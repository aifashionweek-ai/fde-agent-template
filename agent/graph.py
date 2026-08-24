"""LangGraph agent: guard_input -> plan -> act (ReAct loop w/ tools) -> [approval] -> finalize (schema-validated)."""
import json
import os

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from .approval import approve_calls, classify_execution
from .guards import (
    GuardError,
    budget_guard,
    extract_retrieved_ids,
    input_guard,
    output_guard,
    redact_pii,
)
from .llm import get_llm
from .memory import recall_context
from .prompts import PLANNER, SYSTEM
from .state import AgentState
from .tools import TOOLS, tool_needs_approval
from .tracing import node_span, tag_run

_llm = None
_tool_node = None
def llm():
    global _llm
    if _llm is None: _llm = get_llm()
    return _llm

@node_span("guard_input")
def guard_input(s: AgentState):
    try:
        clean = input_guard(s["task"])
    except GuardError as e:
        return {"errors": [str(e)], "result": {"answer": f"Refused: {e}", "confidence": 0.0, "citations": [], "actions": []}}
    from .identity import principal_from_env
    principal = principal_from_env()                              # D-033: who is calling (from the auth'd gateway)
    tenant, user = principal.tenant_id, principal.user_id
    mem = recall_context(tenant, user, clean)                     # D-016: long-term memory injected as context
    # D-041: system prompt + memory context are NOT persisted into checkpointed messages — act binds
    # them at the model call. Persisting them once-per-turn made turn 2 on a thread carry
    # system → history → system, which the Anthropic formatter rejects (live multi-turn 500).
    return {"task": clean, "step_count": 0, "tool_calls": 0, "errors": [],
            "principal": principal.as_claims(), "memory_ctx": mem or "",
            "messages": [HumanMessage(clean)]}

@node_span("plan")
def plan(s: AgentState):
    out = llm().invoke(PLANNER.format(task=s["task"])).content
    if isinstance(out, list): out = "".join(b.get("text","") for b in out if isinstance(b, dict))
    try: steps = json.loads(out[out.find("["):out.rfind("]")+1])
    except Exception: steps = [s["task"]]
    return {"plan": steps, "step_count": s.get("step_count",0)+1,
            "messages": [HumanMessage(f"Plan: {json.dumps(steps)}. Execute it.")]}

def _system_message(s: AgentState) -> SystemMessage:
    """The single system message, built fresh per model call (D-041) — never stored in state, so a
    multi-turn thread can never accumulate duplicates. Memory context (D-016) rides inside it."""
    sys = SYSTEM.format(task_context=os.getenv("TASK_CONTEXT", "general"))
    if s.get("memory_ctx"): sys += "\n\n" + s["memory_ctx"]
    return SystemMessage(sys)

@node_span("act")
def act(s: AgentState):
    try:
        budget_guard(s.get("step_count",0), s.get("tool_calls",0))
    except GuardError as e:                               # D-001/D-007: budget breach is a RESULT, not an outage
        return {"errors": s.get("errors",[]) + [str(e)],
                "result": {"answer": f"Stopped: {e}", "confidence": 0.0, "citations": [], "actions": []}}
    msg = llm().bind_tools(TOOLS).invoke([_system_message(s)] + s["messages"])
    tcs = getattr(msg, "tool_calls", []) or []
    return {"messages": [msg], "step_count": s["step_count"]+1, "tool_calls": s.get("tool_calls",0)+len(tcs),
            "needs_approval": any(tool_needs_approval(tc["name"]) for tc in tcs)}

def _principal_ids(s):
    p = s.get("principal") or {}
    return p.get("user_id", "anon"), p.get("tenant_id", "demo"), s.get("run_id", "default")

def _authz_resource(name: str, args: dict) -> dict:
    """Map a side-effect tool call to the resource authorize() checks (D-045). Only submit_action carries a
    subject rule; other actions carry just the tenant. One place, so the pre-gate check and the in-tool
    check agree."""
    if name == "submit_action":
        return {"subject": (args or {}).get("target")}
    return {}

@node_span("approval")
def approval(s: AgentState):                            # D-004 HITL + D-034 approval integrity + D-045 authz-before-gate
    last = s["messages"][-1]
    uid, tenant, run_id = _principal_ids(s)
    # D-045: AUTHORIZE BEFORE THE GATE. A human must never be shown a proposal for an action that was never
    # authorizable. Deny unauthorizable calls here, pre-interrupt; the in-tool authorize() (tools.py) stays
    # as defense-in-depth. Conservative batch policy: if any call in the proposal is unauthorized, the whole
    # proposal is rejected pre-gate (real proposals are single-call).
    from .authz import authorize
    from .identity import principal_from_claims
    principal = principal_from_claims(s.get("principal") or {})
    authz = [(tc, authorize(principal, tc["name"], {"tenant": tenant, **_authz_resource(tc["name"], tc.get("args", {}))}))
             for tc in last.tool_calls if tool_needs_approval(tc["name"])]
    if any(not d.allow for _, d in authz):
        deny = {tc["id"]: d for tc, d in authz}
        return {"needs_approval": False, "messages": [
            ToolMessage(content=json.dumps({"status": "DENIED", "tool": tc["name"],
                "reason": (deny[tc["id"]].reason if tc["id"] in deny and not deny[tc["id"]].allow
                           else "withheld: proposal contains an unauthorized action")}),
                tool_call_id=tc["id"]) for tc in last.tool_calls]}
    # bind approval to the EXACT proposed actions (their proposal hashes), not just "yes to something"
    hashes = approve_calls(last.tool_calls, uid, tenant, run_id, tool_needs_approval)
    approved = list(set(s.get("approved", [])) | hashes)
    if os.getenv("DEMO_AUTOAPPROVE") == "1":            # smooth demos only; real deployments keep this off
        return {"needs_approval": False, "approved": approved, "path": s.get("path", []) + ["approval(auto)"]}
    decision = interrupt({"pending_tool_calls": last.tool_calls, "proposal_hashes": sorted(hashes),
                          "question": "Approve side-effect tool call(s)?"})
    # D-038: over the wire the decision is {"approve": bool, "hashes": [...]} — the hashes the human SAW
    # in the interrupt payload. Approval grants THOSE, not whatever is pending at resume time, so a
    # proposal mutated after being shown can never execute on that approval (tools recomputes and refuses).
    # A bare True (in-process/legacy resume) grants the recomputed pending set.
    if isinstance(decision, dict):
        ok, granted = decision.get("approve") is True, set(decision.get("hashes") or [])
    else:
        ok, granted = decision is True, hashes
    if not ok:
        return {"messages": [ToolMessage(content="Denied by human.", tool_call_id=tc["id"]) for tc in last.tool_calls], "needs_approval": False}
    return {"needs_approval": False, "approved": list(set(s.get("approved", [])) | granted)}

@node_span("finalize")
def finalize(s: AgentState):
    if s.get("result"): return {}
    last = s["messages"][-1].content
    if isinstance(last, list): last = "".join(b.get("text","") for b in last if isinstance(b, dict))
    try:
        raw = json.loads(last[last.find("{"):last.rfind("}")+1])
        return {"result": output_guard(raw, retrieved_ids=extract_retrieved_ids(s["messages"])).model_dump(),
                "path": s.get("path", []) + ["finalize"]}
    except Exception as e:
        return {"result": {"answer": redact_pii(last[:4000] or "no answer"), "confidence": 0.3, "citations": [], "actions": []},
                "errors": s.get("errors",[]) + [f"output_guard: {e}"]}

def route_after_guard(s): return "finalize" if s.get("result") else "plan"
def route_after_act(s):
    if s.get("result"): return "finalize"                 # budget stop
    last = s["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "approval" if s.get("needs_approval") else "tools"
    return "finalize"
def route_after_approval(s):
    last = s["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else "act"

@node_span("tools")                                       # D-044: telemetry span (path label set below is preserved)
def traced_tools(s: AgentState):
    """Wrap ToolNode so tool names land in the trace path (D-013) AND enforce approval integrity +
    idempotency (D-034): a side-effect call executes only if its proposal hash was approved and hasn't run
    before. An unapproved/args-changed call is REFUSED; a replay is an idempotent skip. Read tools pass through."""
    global _tool_node
    if _tool_node is None: _tool_node = ToolNode(TOOLS)
    last = s["messages"][-1]
    calls = getattr(last, "tool_calls", []) or []
    uid, tenant, run_id = _principal_ids(s)
    to_exec, refusals, mark = classify_execution(
        calls, uid, tenant, run_id, set(s.get("approved", [])), set(s.get("executed", [])), tool_needs_approval)
    msgs = [ToolMessage(content=json.dumps({"status": "REFUSED", "reason": reason, "tool": tc["name"]}),
                        tool_call_id=tc["id"]) for tc, reason in refusals]
    if to_exec:
        exec_msg = last.model_copy(update={"tool_calls": to_exec})   # run ToolNode on approved calls only
        node_out = _tool_node.invoke({**s, "messages": s["messages"][:-1] + [exec_msg]})
        msgs.extend(node_out["messages"])
    label = ("tools[" + ",".join(tc["name"] for tc in to_exec) + "]") if to_exec else \
            ("tools(refused)" if refusals else "tools")
    return {"messages": msgs, "path": s.get("path", []) + [label],
            "executed": list(set(s.get("executed", [])) | set(mark))}

def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("guard_input", guard_input); g.add_node("plan", plan); g.add_node("act", act)
    g.add_node("tools", traced_tools); g.add_node("approval", approval); g.add_node("finalize", finalize)
    g.add_edge(START, "guard_input")
    g.add_conditional_edges("guard_input", route_after_guard, {"plan":"plan","finalize":"finalize"})
    g.add_edge("plan", "act")
    g.add_conditional_edges("act", route_after_act, {"tools":"tools","approval":"approval","finalize":"finalize"})
    g.add_conditional_edges("approval", route_after_approval, {"tools":"tools","act":"act"})
    g.add_edge("tools", "act")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())

graph = build_graph()

def run(task: str, thread_id: str = "default", tenant: str | None = None) -> dict:
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": int(os.getenv("MAX_STEPS", 12)) * 3,
           **tag_run(thread_id=thread_id, tenant=tenant or os.getenv("TENANT", "demo"))}
    # D-041: a thread with an UNDECIDED approval refuses new input — you can't talk past a pending
    # proposal (and abandoning its un-answered tool_use breaks the provider's message contract).
    # The same proposal is returned; deciding it via /approve unblocks the thread.
    snap = graph.get_state(cfg)
    pending = [i for t in getattr(snap, "tasks", ()) or () for i in getattr(t, "interrupts", ()) or ()]
    if pending:
        return {"status": "pending_approval", "state": pending, "path": (snap.values or {}).get("path", [])}
    # result=None clears the PREVIOUS run's result on a reused thread — without it, route_after_guard
    # sees the stale result and short-circuits guard_input -> finalize, replaying the old answer (D-038).
    out = graph.invoke({"task": task, "path": [], "run_id": thread_id, "result": None}, config=cfg)
    res = out.get("result")
    if res: res = {**res, "trace": _trace(out, thread_id)}
    return res or {"status": "interrupted", "state": out.get("__interrupt__"), "path": out.get("path", [])}

def _trace(out: dict, thread_id: str) -> dict:
    """Assemble the trace block: node path + step/tool counts, plus the D-044 per-layer spans and run
    totals (real tokens/latency/cost) from the telemetry recorder if present."""
    t = {"path": out.get("path", []), "steps": out.get("step_count"), "tool_calls": out.get("tool_calls")}
    try:
        from . import telemetry
        rec = telemetry.last_run(thread_id)
        if rec: t["spans"] = rec["spans"]; t["totals"] = rec["totals"]
    except Exception:
        pass
    return t

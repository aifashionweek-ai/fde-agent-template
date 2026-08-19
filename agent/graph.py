"""LangGraph agent: guard_input -> plan -> act (ReAct loop w/ tools) -> [approval] -> finalize (schema-validated)."""
import json, os
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from .state import AgentState
from .llm import get_llm
from .tools import TOOLS, tool_needs_approval
from .guards import input_guard, budget_guard, output_guard, extract_retrieved_ids, GuardError
from .tracing import tag_run, node_span
from .prompts import SYSTEM, PLANNER

_llm = None
def llm():
    global _llm
    if _llm is None: _llm = get_llm()
    return _llm

@node_span("guard_input")
def guard_input(s: AgentState):
    try:
        clean = input_guard(s["task"])
        return {"task": clean, "step_count": 0, "tool_calls": 0, "errors": [],
                "messages": [SystemMessage(SYSTEM.format(task_context=os.getenv("TASK_CONTEXT","general"))), HumanMessage(clean)]}
    except GuardError as e:
        return {"errors": [str(e)], "result": {"answer": f"Refused: {e}", "confidence": 0.0, "citations": [], "actions": []}}

@node_span("plan")
def plan(s: AgentState):
    out = llm().invoke(PLANNER.format(task=s["task"])).content
    if isinstance(out, list): out = "".join(b.get("text","") for b in out if isinstance(b, dict))
    try: steps = json.loads(out[out.find("["):out.rfind("]")+1])
    except Exception: steps = [s["task"]]
    return {"plan": steps, "step_count": s.get("step_count",0)+1,
            "messages": [HumanMessage(f"Plan: {json.dumps(steps)}. Execute it.")]}

@node_span("act")
def act(s: AgentState):
    try:
        budget_guard(s.get("step_count",0), s.get("tool_calls",0))
    except GuardError as e:                               # D-001/D-007: budget breach is a RESULT, not an outage
        return {"errors": s.get("errors",[]) + [str(e)],
                "result": {"answer": f"Stopped: {e}", "confidence": 0.0, "citations": [], "actions": []}}
    msg = llm().bind_tools(TOOLS).invoke(s["messages"])
    tcs = getattr(msg, "tool_calls", []) or []
    return {"messages": [msg], "step_count": s["step_count"]+1, "tool_calls": s.get("tool_calls",0)+len(tcs),
            "needs_approval": any(tool_needs_approval(tc["name"]) for tc in tcs)}

@node_span("approval")
def approval(s: AgentState):                            # D-004 human-in-the-loop
    last = s["messages"][-1]
    decision = interrupt({"pending_tool_calls": last.tool_calls, "question": "Approve side-effect tool call(s)?"})
    if decision is not True:
        return {"messages": [ToolMessage(content="Denied by human.", tool_call_id=tc["id"]) for tc in last.tool_calls], "needs_approval": False}
    return {"needs_approval": False}

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
        return {"result": {"answer": last[:4000] or "no answer", "confidence": 0.3, "citations": [], "actions": []},
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

def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("guard_input", guard_input); g.add_node("plan", plan); g.add_node("act", act)
    g.add_node("tools", ToolNode(TOOLS)); g.add_node("approval", approval); g.add_node("finalize", finalize)
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
    out = graph.invoke({"task": task, "path": []}, config=cfg)
    res = out.get("result")
    if res: res = {**res, "trace": {"path": out.get("path", []), "steps": out.get("step_count"), "tool_calls": out.get("tool_calls")}}
    return res or {"status": "interrupted", "state": out.get("__interrupt__"), "path": out.get("path", [])}

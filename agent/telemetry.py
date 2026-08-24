"""Per-layer span recorder (D-044) — OBSERVABILITY ONLY. Additive: this module never changes a control
decision, it watches them. Wired in ONE place (agent/tracing.py node_span) so instrumentation isn't
scattered through the graph, plus a RecordingLLM proxy (agent/llm.py) that captures REAL provider token
usage (not estimates) from LangChain `usage_metadata`.

Per span we record: layer name, kind (MODEL|CODE), tokens_in/out, latency_ms, control status
(PASS|GATED|DENIED|REFUSED|SWAYED), and for the tools layer a per-tool breakdown (name, redacted args,
tokens, ms, short result, status) with the proposal_hash at the gate and the recomputed hash + match at
execute. Emitted args/results are PII-redacted and length-capped (J-07 mindset); the principal is never
emitted.

The active run is a ContextVar so concurrent requests don't cross streams. LAST_RUNS keeps the most
recent serialized trace per thread for GET /trace/{thread_id} and the dashboard.
"""
from __future__ import annotations
import contextvars
import json
import os
import time
from dataclasses import dataclass, field, asdict

from .guards import redact_pii

# node name -> (display layer name, kind). Anything not listed defaults to (name, "CODE").
_LAYER = {
    "guard_input": ("guard_input", "CODE"),
    "plan":        ("plan", "MODEL"),
    "act":         ("act", "MODEL"),
    "tools":       ("tools", "CODE"),
    "approval":    ("approval_gate", "CODE"),
    "finalize":    ("finalize", "CODE"),
}

# Configurable cost rate (USD per 1M tokens). Defaults ~ Claude Sonnet list price; override via env.
_COST_IN  = float(os.getenv("COST_PER_1M_INPUT", "3.0"))
_COST_OUT = float(os.getenv("COST_PER_1M_OUTPUT", "15.0"))

LAST_RUNS: dict[str, dict] = {}                 # thread_id -> serialized trace (for /trace/{id} + dashboard)


@dataclass
class ToolRecord:
    name: str
    args: dict
    tokens_in: int = 0
    tokens_out: int = 0
    ms: float | None = None
    result: str = ""
    status: str = "PASS"
    proposal_hash: str | None = None
    recomputed_hash: str | None = None
    hash_match: bool | None = None


@dataclass
class Span:
    layer: str
    kind: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    status: str = "PASS"
    proposal_hashes: list[str] = field(default_factory=list)
    tools: list[ToolRecord] = field(default_factory=list)
    _t0: float = 0.0


@dataclass
class RunTrace:
    thread_id: str
    spans: list[Span] = field(default_factory=list)
    stack: list[Span] = field(default_factory=list)


_RUNS: dict[str, RunTrace] = {}
_ACTIVE: contextvars.ContextVar = contextvars.ContextVar("active_run", default=None)


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return round(tokens_in / 1e6 * _COST_IN + tokens_out / 1e6 * _COST_OUT, 6)


def _redact_args(args: dict | None) -> dict:
    """Emit-safe args: PII-redacted string values, length-capped. Never emit a raw principal blob."""
    out = {}
    for k, v in (args or {}).items():
        if k in {"principal", "claims", "token", "authorization"}:
            out[k] = "[REDACTED]"
        elif isinstance(v, str):
            out[k] = redact_pii(v)[:200]
        else:
            out[k] = v
    return out


def _short(s, n: int = 240) -> str:
    return redact_pii(str(s))[:n]


# ---------- run/span lifecycle (called from tracing.node_span) ----------
def record_model_usage(tokens_in: int, tokens_out: int) -> None:
    """Called by RecordingLLM after each model call — attributes REAL tokens to the active span."""
    run = _ACTIVE.get()
    if not run or not run.stack:
        return
    sp = run.stack[-1]
    sp.tokens_in += int(tokens_in or 0)
    sp.tokens_out += int(tokens_out or 0)


def open_span(node_name: str, thread_id: str, state: dict) -> Span:
    layer, kind = _LAYER.get(node_name, (node_name, "CODE"))
    run = _RUNS.get(thread_id)
    if run is None or node_name == "guard_input":       # guard_input begins a fresh top-level run
        run = RunTrace(thread_id=thread_id)
        _RUNS[thread_id] = run
    _ACTIVE.set(run)
    sp = Span(layer=layer, kind=kind, _t0=time.perf_counter())
    run.stack.append(sp)
    if node_name == "approval":                         # gate hashes must be captured even if it interrupts
        sp.proposal_hashes = _gate_hashes(state)
    return sp


def close_span(sp: Span, node_name: str, state: dict, out: dict | None, error: BaseException | None) -> None:
    sp.latency_ms = round((time.perf_counter() - sp._t0) * 1000, 2)
    if error is not None:
        # GraphInterrupt (approval pause) is the expected 'GATED' path, not a failure.
        sp.status = "GATED" if error.__class__.__name__ in {"GraphInterrupt", "Interrupt"} else "ERROR"
    else:
        run0 = _ACTIVE.get()
        if node_name == "tools":
            sp.tools = _tool_records(state, out)
            sp.status = _tools_status(sp.tools, run0)
        else:
            sp.status = _status_for(node_name, state, out, run0)
    run = _ACTIVE.get()
    if run and run.stack:
        run.stack.pop()
        run.spans.append(sp)
        LAST_RUNS[run.thread_id] = serialize(run)       # persist after every node → /trace always current


# ---------- status + tool extraction (reads state/out only; no control change) ----------
def _principal_ids(state: dict):
    p = (state or {}).get("principal") or {}
    return p.get("user_id", "anon"), p.get("tenant_id", "demo"), (state or {}).get("run_id", "default")


def _gate_hashes(state: dict) -> list[str]:
    try:
        from .approval import approve_calls
        from .tools import tool_needs_approval
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None) or []
        uid, tenant, run_id = _principal_ids(state)
        return sorted(approve_calls(calls, uid, tenant, run_id, tool_needs_approval))
    except Exception:
        return []


def _had_retrieval(run: RunTrace | None) -> bool:
    return bool(run) and any(t.name in {"search_kb", "recall", "lookup"}
                             for s in run.spans for t in s.tools)


def _status_for(node_name: str, state: dict, out: dict | None, run: RunTrace | None = None) -> str:
    out = out or {}
    if node_name == "guard_input":
        res = out.get("result") or {}
        return "DENIED" if str(res.get("answer", "")).startswith("Refused") else "PASS"
    if node_name == "approval":
        # GATED is the interrupt (error) path (set in close_span). A NORMAL return here means either the
        # human decision resolved (resume/auto), OR a D-045 pre-gate authz denial (the human was never
        # shown the proposal). Denied-pre-gate after untrusted retrieval is SWAYED (the D-043 signature).
        for m in out.get("messages", []) or []:
            c = getattr(m, "content", "")
            if "Denied by human" in c:
                return "DENIED"
            if '"status": "DENIED"' in c:                # pre-gate authz denial
                return "SWAYED" if _had_retrieval(run) else "DENIED"
        return "PASS"
    return "PASS"


def _tools_status(recs: list[ToolRecord], run: RunTrace | None) -> str:
    """Span status for a tools node. SWAYED = an action was DENIED/REFUSED in a run that had already
    retrieved (untrusted) content — i.e. the model was talked into a bad action by retrieved data, and a
    deterministic control caught it (the D-043 signature). A direct denial with no prior retrieval is
    plain DENIED/REFUSED."""
    blocked = [r for r in recs if r.status in ("DENIED", "REFUSED")]
    if not blocked:
        return "PASS"
    if _had_retrieval(run):
        return "SWAYED"
    return "REFUSED" if any(r.status == "REFUSED" for r in blocked) else "DENIED"


def _tool_records(state: dict, out: dict | None) -> list[ToolRecord]:
    out = out or {}
    try:
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None) or []
    except Exception:
        calls = []
    msgs = out.get("messages", []) or []
    by_id = {getattr(m, "tool_call_id", None): m for m in msgs}
    uid, tenant, run_id = _principal_ids(state)
    newly_exec = set(out.get("executed", [])) - set(state.get("executed", []))
    from .approval import proposal_hash
    from .tools import tool_needs_approval
    recs = []
    for tc in calls:
        name, args = tc.get("name"), tc.get("args", {})
        m = by_id.get(tc.get("id"))
        content = getattr(m, "content", "") if m else ""
        status = "PASS"
        if '"status": "REFUSED"' in content or "REFUSED" in content:
            status = "REFUSED"
        elif '"status": "DENIED"' in content or '"DENIED"' in content:
            status = "DENIED"
        rec = ToolRecord(name=name, args=_redact_args(args), result=_short(content), status=status)
        if tool_needs_approval(name):
            h = proposal_hash(name, args, uid, tenant, run_id)
            rec.proposal_hash = h
            if status != "REFUSED":                     # it actually executed (PASS or authz-DENIED inside)
                rec.recomputed_hash = h                  # → recompute + match makes D-034 binding visible
                rec.hash_match = h in newly_exec
        recs.append(rec)
    if len(recs) == 1:                                   # single-tool node → its ms IS the node ms (real)
        recs[0].ms = None                                # filled by caller via span latency (see serialize note)
    return recs


# ---------- serialization ----------
def serialize(run: RunTrace) -> dict:
    spans = []
    for sp in run.spans:
        d = {"layer": sp.layer, "kind": sp.kind, "tokens_in": sp.tokens_in, "tokens_out": sp.tokens_out,
             "latency_ms": sp.latency_ms, "status": sp.status}
        if sp.proposal_hashes:
            d["proposal_hashes"] = sp.proposal_hashes
        if sp.tools:
            tl = []
            for r in sp.tools:
                rd = {k: v for k, v in asdict(r).items() if v is not None and not (k == "args" and not v)}
                if len(sp.tools) == 1 and r.ms is None:  # attribute the node's real ms to the sole tool
                    rd["ms"] = sp.latency_ms
                tl.append(rd)
            d["tools"] = tl
        spans.append(d)
    ti = sum(s["tokens_in"] for s in spans)
    to = sum(s["tokens_out"] for s in spans)
    ms = round(sum(s["latency_ms"] for s in spans), 2)
    return {"thread_id": run.thread_id, "spans": spans,
            "totals": {"tokens_in": ti, "tokens_out": to, "tokens": ti + to,
                       "latency_ms": ms, "cost_usd": cost_usd(ti, to)}}


def last_run(thread_id: str) -> dict | None:
    return LAST_RUNS.get(thread_id)


# ---------- LLM proxy: real token capture at ONE point ----------
class RecordingLLM:
    """Transparent proxy around a chat model. Records REAL provider token usage into the active span and
    delegates everything else unchanged — it cannot alter a model output or a control decision."""

    def __init__(self, inner):
        self._inner = inner

    def bind_tools(self, *a, **k):
        return RecordingLLM(self._inner.bind_tools(*a, **k))

    def invoke(self, *a, **k):
        resp = self._inner.invoke(*a, **k)
        um = getattr(resp, "usage_metadata", None) or {}
        if um:
            record_model_usage(um.get("input_tokens", 0), um.get("output_tokens", 0))
        return resp

    def __getattr__(self, name):
        return getattr(self._inner, name)

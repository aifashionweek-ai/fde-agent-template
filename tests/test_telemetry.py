"""D-044 guard: the per-layer telemetry recorder observes every node faithfully and never lies about
numbers. One span per node; token totals reconcile with the provider usage_metadata (not estimates);
CODE layers are 0-token; proposal hashes appear at the gate and the recomputed-hash+match at execute;
emitted tool args are PII-redacted. Telemetry is observation only — it must not change control flow."""
import json
import uuid

import pytest
from langchain_core.messages import AIMessage, ToolMessage

import agent.graph as g
from agent import telemetry
from agent.telemetry import RecordingLLM, _redact_args, cost_usd


class UsageLLM:
    """Scripted model that also reports REAL-shaped usage_metadata, so token capture has something to
    reconcile against. plan: 10/5, each act: 20/8."""
    def __init__(self, proposer):
        self.proposer = proposer
    def bind_tools(self, tools):
        return self
    def invoke(self, x):
        if isinstance(x, str):
            return AIMessage(content='["do it"]', usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
        msg = self.proposer(x)
        msg.usage_metadata = {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28}
        return msg


def _answer_directly(x):
    return AIMessage(content=json.dumps({"answer": "done", "confidence": 0.2, "citations": [], "actions": []}))


def _reset_then_report(x):
    if isinstance(x[-1], ToolMessage):
        return AIMessage(content=json.dumps({"answer": f"outcome: {x[-1].content}", "confidence": 0.2,
                                             "citations": [], "actions": []}))
    return AIMessage(content="", tool_calls=[{"name": "reset_access",
        "args": {"employee_id": "alice", "system": "vpn"}, "id": "r1", "type": "tool_call"}])


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("DEMO_AUTOAPPROVE", raising=False)
    monkeypatch.setenv("USER_ID", "alice")
    monkeypatch.setenv("TENANT", "meridian")
    telemetry._RUNS.clear(); telemetry.LAST_RUNS.clear()


def test_one_span_per_node_and_token_reconciliation(monkeypatch):
    monkeypatch.setattr(g, "_llm", RecordingLLM(UsageLLM(_answer_directly)))
    tid = str(uuid.uuid4())
    out = g.run("answer me", thread_id=tid)
    trace = telemetry.last_run(tid)
    layers = [s["layer"] for s in trace["spans"]]
    assert layers == ["guard_input", "plan", "act", "finalize"]      # one span per node, in order
    # token totals reconcile with what the model reported: plan 10/5 + act 20/8
    assert trace["totals"]["tokens_in"] == 30 and trace["totals"]["tokens_out"] == 13
    assert trace["totals"]["tokens"] == 43
    # CODE layers carry zero model tokens; MODEL layers carry the real usage
    by = {s["layer"]: s for s in trace["spans"]}
    assert by["guard_input"]["tokens_in"] == 0 and by["finalize"]["tokens_out"] == 0
    assert by["plan"]["tokens_in"] == 10 and by["act"]["tokens_out"] == 8
    assert by["plan"]["kind"] == "MODEL" and by["guard_input"]["kind"] == "CODE"
    # cost is computed from the configurable rate, not asserted
    assert trace["totals"]["cost_usd"] == cost_usd(30, 13)


def test_latency_is_recorded_positive(monkeypatch):
    monkeypatch.setattr(g, "_llm", RecordingLLM(UsageLLM(_answer_directly)))
    tid = str(uuid.uuid4())
    g.run("answer me", thread_id=tid)
    trace = telemetry.last_run(tid)
    assert all(s["latency_ms"] >= 0 for s in trace["spans"])
    assert trace["totals"]["latency_ms"] >= 0


def test_gate_and_execute_hashes_present(monkeypatch):
    monkeypatch.setattr(g, "_llm", RecordingLLM(UsageLLM(_reset_then_report)))
    from api.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    tid = str(uuid.uuid4())
    out = client.post("/run", json={"task": "reset my access", "thread_id": tid}).json()
    hashes = out["state"][0]["value"]["proposal_hashes"]
    # gate span recorded the proposal hash(es) even though the node interrupted
    trace = telemetry.last_run(tid)
    gate = [s for s in trace["spans"] if s["layer"] == "approval_gate"][0]
    assert gate["status"] == "GATED" and gate["proposal_hashes"] == hashes
    # approve → execute; the tools span tool record carries recomputed hash + match=True
    client.post("/approve", json={"thread_id": tid, "approve": True, "hashes": hashes})
    trace = telemetry.last_run(tid)
    tools = [s for s in trace["spans"] if s["layer"] == "tools" and s.get("tools")][-1]
    rec = tools["tools"][0]
    assert rec["name"] == "reset_access"
    assert rec["proposal_hash"] in hashes
    assert rec["recomputed_hash"] == rec["proposal_hash"] and rec["hash_match"] is True


def test_emitted_tool_args_are_pii_redacted():
    red = _redact_args({"summary": "contact a@b.com ssn 123-45-6789", "principal": {"user": "x"}})
    assert "a@b.com" not in red["summary"] and "123-45-6789" not in red["summary"]
    assert "[EMAIL]" in red["summary"] and "[SSN]" in red["summary"]
    assert red["principal"] == "[REDACTED]"


def test_trace_endpoint_and_dashboard_served(monkeypatch):
    monkeypatch.setattr(g, "_llm", RecordingLLM(UsageLLM(_answer_directly)))
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    tid = str(uuid.uuid4())
    client.post("/run", json={"task": "answer me", "thread_id": tid})
    r = client.get(f"/trace/{tid}")
    assert r.status_code == 200 and r.json()["totals"]["tokens"] == 43
    assert client.get("/trace/nonexistent").status_code == 404
    assert "observability" in client.get("/dashboard").text     # dashboard page served


def test_captured_fixtures_are_wellformed_and_show_the_controls():
    """The committed offline fixtures (scripts/capture_runs.py output) must carry the demo artifacts:
    every scenario has spans+totals; the cross-user reset is DENIED with a hash match; the injection
    tools span is SWAYED; the mutate reset is REFUSED with no match."""
    import pathlib
    f = pathlib.Path(__file__).resolve().parent.parent / "evals" / "fixtures" / "telemetry_runs.json"
    runs = json.loads(f.read_text())
    for key in ("self_reset", "cross_user", "policy_read", "injection", "mutate"):
        assert key in runs and runs[key]["trace"]["spans"] and runs[key]["trace"]["totals"]["tokens"] > 0

    def tools(run):
        return [t for s in run["trace"]["spans"] if s.get("tools") for t in s["tools"]]
    cross = [t for t in tools(runs["cross_user"]) if t["name"] == "reset_access"][0]
    assert cross["status"] == "DENIED" and cross["hash_match"] is True      # executed, authz denied inside
    inj_span = [s for s in runs["injection"]["trace"]["spans"] if s["layer"] == "tools" and s["status"] == "SWAYED"]
    assert inj_span, "injection run should have a SWAYED tools span"
    mut = [t for t in tools(runs["mutate"]) if t["name"] == "reset_access"][0]
    assert mut["status"] == "REFUSED" and mut.get("hash_match") in (None, False)  # never executed (key omitted when None)


def test_telemetry_failure_never_breaks_a_run(monkeypatch):
    """Observation must never take down a run: if the recorder raises, the run still returns."""
    monkeypatch.setattr(g, "_llm", RecordingLLM(UsageLLM(_answer_directly)))
    monkeypatch.setattr(telemetry, "open_span", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = g.run("answer me", thread_id=str(uuid.uuid4()))
    assert out["answer"] == "done"                                   # control path unharmed

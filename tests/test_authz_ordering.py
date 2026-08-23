"""D-045 guard: authorization runs BEFORE the human approval gate. A human must never be shown a
proposal for an action that was never authorizable (wasted approval + wider attack surface). Cross-user
reset (alice->bob) is denied pre-gate — it never reaches interrupt(). The in-tool authorize() stays as
defense-in-depth (belt and suspenders), so removing EITHER check still denies."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

import agent.graph as g
from agent import telemetry
from api.main import app


class ResetsBob:
    """Model proposes resetting BOB's access (cross-user) as alice, then reports the tool result."""
    def bind_tools(self, tools): return self
    def invoke(self, x):
        if isinstance(x, str): return AIMessage(content='["reset bob"]')
        if isinstance(x[-1], ToolMessage):
            return AIMessage(content=json.dumps({"answer": f"outcome: {x[-1].content}", "confidence": 0.1,
                                                 "citations": [], "actions": []}))
        return AIMessage(content="", tool_calls=[{"name": "reset_access",
            "args": {"employee_id": "bob", "system": "vpn"}, "id": "b1", "type": "tool_call"}])


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(g, "_llm", ResetsBob())
    monkeypatch.delenv("DEMO_AUTOAPPROVE", raising=False)
    monkeypatch.setenv("USER_ID", "alice")               # non-admin caller
    monkeypatch.setenv("TENANT", "meridian")
    monkeypatch.delenv("ROLES", raising=False)
    telemetry._RUNS.clear(); telemetry.LAST_RUNS.clear()
    return TestClient(app)


def test_cross_user_never_reaches_the_approval_gate(client):
    tid = str(uuid.uuid4())
    out = client.post("/run", json={"task": "reset bob's vpn access", "thread_id": tid}).json()
    # RED before the fix: this returned status=interrupted (the human was shown the proposal).
    assert out.get("status") != "interrupted", "cross-user proposal reached the human gate"
    assert "result" in out
    body = json.dumps(out)
    assert "DENIED" in body or "cannot reset" in body    # denied pre-gate
    assert "queued" not in body                           # never executed


def test_telemetry_shows_pre_gate_denial_not_gated(client):
    tid = str(uuid.uuid4())
    client.post("/run", json={"task": "reset bob's vpn access", "thread_id": tid})
    trace = telemetry.last_run(tid)
    gate = [s for s in trace["spans"] if s["layer"] == "approval_gate"]
    assert gate, "expected an approval_gate span"
    assert all(s["status"] == "DENIED" for s in gate)    # DENIED pre-gate, never GATED (no human prompt)


def test_self_reset_still_reaches_the_gate(client, monkeypatch):
    """The fix must not over-block: an AUTHORIZED action (self-reset) still reaches the human gate."""
    class ResetsSelf(ResetsBob):
        def invoke(self, x):
            if isinstance(x, str): return AIMessage(content='["reset self"]')
            if isinstance(x[-1], ToolMessage):
                return AIMessage(content=json.dumps({"answer": "ok", "confidence": 0.1, "citations": [], "actions": []}))
            return AIMessage(content="", tool_calls=[{"name": "reset_access",
                "args": {"employee_id": "alice", "system": "vpn"}, "id": "a1", "type": "tool_call"}])
    monkeypatch.setattr(g, "_llm", ResetsSelf())
    out = client.post("/run", json={"task": "reset my vpn access", "thread_id": str(uuid.uuid4())}).json()
    assert out.get("status") == "interrupted"            # authorized -> human IS asked

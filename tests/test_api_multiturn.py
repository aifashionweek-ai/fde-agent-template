"""D-041 guard: multi-turn threads are valid and the API never emits a bare plain-text 500.

Defect (live repro): turn 2 on an existing thread 500'd in act — guard_input PERSISTED the system
prompt into checkpointed state each turn, so the history became system → ... → system and
langchain_anthropic rejected it ("multiple non-consecutive system messages"). The fix binds the
system prompt (and memory context) at the model call, never into state — a duplicate is structurally
impossible. These tests assert the formatter's contract on what act actually sends, so they stay
deterministic (no live model): exactly ONE system message, at position 0, on EVERY act call."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, SystemMessage

import agent.graph as g
import api.main as api
from api.main import app
from tests.llm_stub import ScriptedLLM


class RecordingFinalLLM:
    """Answers directly (no tools) and RECORDS every act invocation's message list."""

    def __init__(self):
        self.act_inputs = []

    def bind_tools(self, tools):
        return self

    def invoke(self, input):
        if isinstance(input, str):                       # plan node
            return AIMessage(content='["answer directly"]')
        self.act_inputs.append(list(input))              # act node — capture what the model would see
        return AIMessage(content=json.dumps(
            {"answer": "ok - noted.", "confidence": 0.2, "citations": [], "actions": []}))


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.delenv("DEMO_AUTOAPPROVE", raising=False)
    monkeypatch.setenv("USER_ID", "alice")
    monkeypatch.setenv("TENANT", "meridian")
    return monkeypatch


def _assert_anthropic_valid(act_inputs):
    """The exact contract the Anthropic formatter enforces, checked deterministically."""
    assert act_inputs, "act was never called"
    for msgs in act_inputs:
        sys_idx = [i for i, m in enumerate(msgs) if isinstance(m, SystemMessage)]
        assert sys_idx == [0], f"expected exactly one system message at position 0, got {sys_idx}"


def test_second_turn_same_thread_is_valid_and_single_system(env):
    rec = RecordingFinalLLM()
    env.setattr(g, "_llm", rec)
    client = TestClient(app)
    tid = str(uuid.uuid4())
    r1 = client.post("/run", json={"task": "Please note my badge number is 7741.", "thread_id": tid})
    assert r1.status_code == 200 and "result" in r1.json()
    r2 = client.post("/run", json={"task": "What badge number did I give you?", "thread_id": tid})
    assert r2.status_code == 200, r2.text                # LIVE REPRO: this was a plain-text 500
    assert "result" in r2.json()
    _assert_anthropic_valid(rec.act_inputs)
    # multi-turn context: turn 2's model call still contains turn 1's conversation
    turn2 = rec.act_inputs[-1]
    assert any("7741" in str(getattr(m, "content", "")) for m in turn2 if not isinstance(m, SystemMessage))


def test_turn_after_interrupted_and_approved_turn_is_valid(env):
    env.setattr(g, "_llm", ScriptedLLM())
    client = TestClient(app)
    tid = str(uuid.uuid4())
    out = client.post("/run", json={"task": "reset my vpn access", "thread_id": tid}).json()
    assert out["status"] == "interrupted"
    hashes = out["state"][0]["value"]["proposal_hashes"]
    res = client.post("/approve", json={"thread_id": tid, "approve": True, "hashes": hashes}).json()
    assert "queued" in res["result"]["answer"]
    # follow-up turn on the SAME thread (history now holds system+tool traffic from turn 1)
    rec = RecordingFinalLLM()
    env.setattr(g, "_llm", rec)
    r2 = client.post("/run", json={"task": "what did you just do for me?", "thread_id": tid})
    assert r2.status_code == 200, r2.text
    assert "result" in r2.json()
    _assert_anthropic_valid(rec.act_inputs)


def test_new_input_on_pending_approval_returns_the_proposal_not_a_crash(env):
    """A thread with an UNDECIDED approval refuses new input (you can't talk past a pending proposal —
    abandoning the un-answered tool_use also breaks the Anthropic message contract, live 400). The
    client gets the same proposal back as status=pending_approval; deciding it unblocks the thread."""
    env.setattr(g, "_llm", ScriptedLLM())
    client = TestClient(app)
    tid = str(uuid.uuid4())
    out = client.post("/run", json={"task": "reset my vpn access", "thread_id": tid}).json()
    assert out["status"] == "interrupted"
    hashes = out["state"][0]["value"]["proposal_hashes"]
    r2 = client.post("/run", json={"task": "actually, what is the vpn policy?", "thread_id": tid})
    assert r2.status_code == 200, r2.text
    out2 = r2.json()
    assert out2["status"] == "pending_approval"
    assert out2["state"][0]["value"]["proposal_hashes"] == hashes   # the SAME undecided proposal
    # deciding it unblocks the thread
    res = client.post("/approve", json={"thread_id": tid, "approve": True, "hashes": hashes}).json()
    assert "queued" in res["result"]["answer"]


def test_crafted_tool_loop_returns_cleanly_not_unbounded(env):
    """D-001/D-007 confirming (graph-level): a model that proposes a read tool forever is bounded —
    budget_guard in act stops it (recursion_limit is the backstop). RETURNS a structured result, never hangs."""
    class LoopLLM:
        def bind_tools(self, tools): return self
        def invoke(self, x):
            if isinstance(x, str): return AIMessage(content='["loop"]')
            return AIMessage(content="", tool_calls=[{"name": "calculate",
                "args": {"expression": "1+1"}, "id": "c", "type": "tool_call"}])
    env.setattr(g, "_llm", LoopLLM())
    client = TestClient(app)
    r = client.post("/run", json={"task": "loop forever", "thread_id": str(uuid.uuid4())})
    assert r.status_code == 200
    out = r.json()["result"]
    assert out["confidence"] == 0.0 and "Stopped" in out["answer"]   # bounded, clean, structured


def test_run_unexpected_exception_is_structured_json(env):
    def boom(*a, **k):
        raise RuntimeError("synthetic failure")
    env.setattr(api, "run", boom)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/run", json={"task": "x", "thread_id": "t-err"})
    assert r.status_code == 500
    body = r.json()                                      # RED before fix: plain-text 500, not JSON
    assert body["error"] == "RuntimeError"
    assert body["thread_id"] == "t-err"
    assert "synthetic failure" in body["detail"]


def test_approve_unexpected_exception_is_structured_json(env):
    def boom(*a, **k):
        raise RuntimeError("resume failure")
    env.setattr(api.graph, "invoke", boom)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/approve", json={"thread_id": "t-err2", "approve": True, "hashes": []})
    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "RuntimeError" and body["thread_id"] == "t-err2"

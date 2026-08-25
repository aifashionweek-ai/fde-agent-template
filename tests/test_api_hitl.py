"""D-038 guard — the HITL wire-protocol binding, proven over the real API.

/run's interrupt exposes the `proposal_hashes` the human sees; `/approve {approve, hashes}` grants ONLY
those hashes. A bare approve, an empty hash list, or a wrong/extra hash executes NOTHING — the tools node
recomputes each proposal hash and REFUSES anything not in the approved set. Approval binds to WHAT WAS SEEN
over the wire, never to what happens to be pending at resume time.

Real graph + real FastAPI via TestClient; only the LLM is scripted (tests/llm_stub.py). The ScriptedLLM
proposes submit_action on the caller's OWN target, so it is authorized (D-045) and reaches the gate.

Catch-proof (verified red-first): if the approval node bound to the recomputed pending set instead of the
seen hashes — `granted = hashes` in agent/graph.py::approval instead of `granted = decision["hashes"]` —
then test_approve_with_a_wrong_hash / test_bare_approve would EXECUTE and this suite goes red.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

import agent.graph as g
from agent import telemetry
from agent.approval import proposal_hash
from api.main import app
from tests.llm_stub import ScriptedLLM

_ARGS = {"target": "alice", "detail": "x"}      # what the ScriptedLLM proposes (submit_action)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(g, "_llm", ScriptedLLM())
    monkeypatch.delenv("DEMO_AUTOAPPROVE", raising=False)     # never auto-approve — we drive the gate
    monkeypatch.setenv("USER_ID", "alice"); monkeypatch.setenv("TENANT", "demo")
    telemetry._RUNS.clear(); telemetry.LAST_RUNS.clear()
    return TestClient(app)


def _seen_hash(thread_id: str) -> str:
    # run_id == thread_id (agent.graph.run); principal alice/demo — this is the hash shown to the human.
    return proposal_hash("submit_action", _ARGS, "alice", "demo", thread_id)


def _propose(client, thread_id):
    return client.post("/run", json={"task": "do it", "thread_id": thread_id}).json()


def test_run_exposes_the_proposal_hash_to_the_human(client):
    tid = str(uuid.uuid4())
    out = _propose(client, tid)
    assert out.get("status") == "interrupted", out
    assert _seen_hash(tid) in json.dumps(out)                # the hash to echo back is in what they saw


def test_approve_with_the_seen_hash_executes(client):
    tid = str(uuid.uuid4())
    _propose(client, tid)
    resp = client.post("/approve", json={"thread_id": tid, "approve": True, "hashes": [_seen_hash(tid)]}).json()
    blob = json.dumps(resp)
    assert "queued" in blob                                  # submit_action actually ran
    assert "tools[submit_action]" in blob                    # executed branch in the trace path
    assert "REFUSED" not in blob


def test_approve_with_a_wrong_hash_is_refused(client):
    tid = str(uuid.uuid4())
    _propose(client, tid)
    # a well-formed hash the human never saw — approval must not honor it
    resp = client.post("/approve", json={"thread_id": tid, "approve": True, "hashes": ["ab" * 32]}).json()
    blob = json.dumps(resp)
    assert "REFUSED" in blob and "queued" not in blob
    assert "tools(refused)" in blob


def test_bare_approve_without_the_seen_hashes_executes_nothing(client):
    """approve:true alone is not enough — the binding is to what was SEEN, so an empty hash list refuses."""
    tid = str(uuid.uuid4())
    _propose(client, tid)
    resp = client.post("/approve", json={"thread_id": tid, "approve": True, "hashes": []}).json()
    blob = json.dumps(resp)
    assert "REFUSED" in blob and "queued" not in blob


def test_deny_executes_nothing(client):
    tid = str(uuid.uuid4())
    _propose(client, tid)
    resp = client.post("/approve", json={"thread_id": tid, "approve": False, "hashes": [_seen_hash(tid)]}).json()
    assert "queued" not in json.dumps(resp)

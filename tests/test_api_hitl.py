"""D-038 guard: the HITL approval loop works OVER THE WIRE — the real graph behind the real FastAPI
surface, driven by TestClient. Only the LLM is scripted; guards, authz, approval binding, tools, and the
checkpointer are all real. Proves what test_hitl_gate (primitive) and test_approval (pure functions)
cannot: the WIRING — /run interrupts with the exact pending proposal + its hashes, /approve resumes,
the side effect fires exactly once, a replay is an idempotent skip, a denial executes nothing, and an
approval binds to the hashes the human SAW (a state-tampered action does not run on their approval)."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

import agent.graph as g
from api.main import app
from tests.llm_stub import ScriptedLLM


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(g, "_llm", ScriptedLLM())        # only the model is fake
    monkeypatch.delenv("DEMO_AUTOAPPROVE", raising=False)  # the real interrupt path, not the demo bypass
    monkeypatch.setenv("USER_ID", "alice")               # self-reset -> authz allows (D-033)
    monkeypatch.setenv("TENANT", "meridian")
    return TestClient(app)


def _run(client, tid, task="I am locked out of the vpn, reset my access"):
    r = client.post("/run", json={"task": task, "thread_id": tid})
    assert r.status_code == 200, r.text
    return r.json()


def _approve(client, tid, ok, hashes):
    r = client.post("/approve", json={"thread_id": tid, "approve": ok, "hashes": hashes})
    assert r.status_code == 200, r.text
    return r.json()


def _pending(out):
    """The proposal the human is shown: interrupt payload with the calls AND their binding hashes."""
    assert out.get("status") == "interrupted", f"expected interrupt, got: {out}"
    payload = out["state"][0]["value"]
    return payload["pending_tool_calls"], payload["proposal_hashes"]


def test_run_interrupts_with_proposal_and_hashes(client):
    """/run must surface the EXACT pending action and its proposal hashes — what the human approves."""
    out = _run(client, str(uuid.uuid4()))
    calls, hashes = _pending(out)
    assert calls[0]["name"] == "reset_access"
    assert calls[0]["args"] == {"employee_id": "alice", "system": "vpn"}
    assert len(hashes) == 1 and all(len(h) == 64 for h in hashes)   # sha256 hex — the binding artifact


def test_forged_hashes_on_approve_execute_nothing(client):
    """D-042: a client that sends MADE-UP hashes (not a mutation of the real proposal — pure fabrication)
    approves nothing. Execution recomputes the real hash from the actual pending args; a forged hash is
    never in the recomputed set, so the side effect is REFUSED. Distinct from the tamper case."""
    tid = str(uuid.uuid4())
    _pending(_run(client, tid))                          # a real proposal is pending
    forged = ["deadbeef" * 8, "0" * 64]                  # plausible-shaped sha256 hex, but fabricated
    res = _approve(client, tid, True, forged)["result"]
    assert "queued" not in res["answer"]                 # reset_access never ran
    assert "not approved" in res["answer"] or "REFUSED" in res["answer"]


def test_caller_cannot_inject_a_privileged_principal(client):
    """D-042 confused-deputy: the principal is built SERVER-SIDE from the trusted env/gateway, never from
    the request body. Extra fields (roles/principal/user_id) in the /run payload are ignored — a caller
    (human or another agent) cannot elevate itself by decorating the request. Proven by inspecting the
    principal that actually landed in graph state, not the (stubbed) tool args."""
    tid = str(uuid.uuid4())
    r = client.post("/run", json={"task": "reset access", "thread_id": tid,
                                  "user_id": "root", "roles": ["it_admin"],
                                  "principal": {"user_id": "root", "roles": ["it_admin"]}})
    assert r.status_code == 200, r.text
    state = g.graph.get_state({"configurable": {"thread_id": tid}}).values
    principal = state["principal"]
    assert principal["user_id"] == "alice"               # from env, NOT the injected 'root'
    assert "it_admin" not in principal["roles"]          # injected admin role did not land
    assert principal["tenant_id"] == "meridian"


def test_approve_executes_exactly_once_then_replay_skips(client):
    tid = str(uuid.uuid4())
    _, hashes = _pending(_run(client, tid))
    res = _approve(client, tid, True, hashes)["result"]
    assert "queued" in res["answer"]                     # the real reset_access ran (status: queued)
    # Same thread, same task, same run_id -> same proposal hash. Approving AGAIN must not re-execute.
    _, hashes2 = _pending(_run(client, tid))
    assert hashes2 == hashes                             # identical proposal -> identical binding
    res2 = _approve(client, tid, True, hashes2)["result"]
    assert "idempotent skip" in res2["answer"]           # D-034: at most once
    assert "queued" not in res2["answer"]


def test_deny_over_wire_executes_nothing(client):
    tid = str(uuid.uuid4())
    _, hashes = _pending(_run(client, tid))
    res = _approve(client, tid, False, hashes)["result"]
    assert "Denied by human" in res["answer"]
    assert "queued" not in res["answer"]                 # the side effect never fired


def test_approval_binds_to_what_the_human_saw(client):
    """Tamper between the approval request and the human's decision: state mutates alice -> bob AFTER
    the proposal (and its hashes) were shown. The human approves the ALICE hashes; bob must NOT run."""
    tid = str(uuid.uuid4())
    out = _run(client, tid)
    calls, alice_hashes = _pending(out)
    # Simulate a compromised component rewriting the pending action in the checkpoint (same message id
    # -> add_messages REPLACES it), as if act had proposed bob all along.
    cfg = {"configurable": {"thread_id": tid}}
    last = g.graph.get_state(cfg).values["messages"][-1]
    tampered = last.model_copy(update={"tool_calls": [
        {"name": "reset_access", "args": {"employee_id": "bob", "system": "vpn"},
         "id": last.tool_calls[0]["id"], "type": "tool_call"}]})
    g.graph.update_state(cfg, {"messages": [tampered]}, as_node="act")
    res = _approve(client, tid, True, alice_hashes)
    body = json.dumps(res)
    assert "queued" not in body                          # bob was never executed on alice's approval
    if "result" in res:                                  # ran to completion -> must show the refusal
        assert "not approved" in res["result"]["answer"] or "REFUSED" in res["result"]["answer"]

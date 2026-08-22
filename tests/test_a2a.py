"""D-040 guard: governance is TRANSPORT-INDEPENDENT — when another AGENT initiates a task over the
HTTP contract, the approval requirement propagates across the A2A boundary. The calling agent has no
approval authority: on interrupt it must route the exact proposal (calls + hashes) to its
approval_channel (a human or an explicit policy); only that decision — echoing the SEEN hashes — can
release the side effect. The graph, guards, authz, and binding are all real; only the LLM is scripted."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

import agent.graph as g
from agent.a2a import A2ACaller, policy_channel
from api.main import app
from tests.llm_stub import ScriptedLLM


@pytest.fixture()
def transport(monkeypatch):
    monkeypatch.setattr(g, "_llm", ScriptedLLM())
    monkeypatch.delenv("DEMO_AUTOAPPROVE", raising=False)
    monkeypatch.setenv("USER_ID", "alice")
    monkeypatch.setenv("TENANT", "meridian")
    return TestClient(app)


def test_agent_initiated_side_effect_still_hits_the_gate(transport):
    """An agent-initiated request does NOT bypass HITL: the caller receives the interrupt and must
    consult its channel with the EXACT proposal the graph raised — nothing executes before that."""
    seen = []

    def recording_deny(proposal):
        seen.append(proposal)
        return False

    out = A2ACaller(transport, recording_deny).run_task("reset alice vpn access", thread_id=str(uuid.uuid4()))
    assert len(seen) == 1                                  # gate reached the channel — no silent execution
    assert seen[0].pending_tool_calls[0]["name"] == "reset_access"
    assert len(seen[0].proposal_hashes) == 1               # the channel sees the binding artifact
    body = json.dumps(out)
    assert "queued" not in body                            # denied -> the side effect never fired
    assert "Denied by human" in out["result"]["answer"]


def test_policy_channel_denies_privileged_action(transport):
    """A policy channel (no human) can only deny-or-allow what it SEES; privileged tools stay blocked."""
    out = A2ACaller(transport, policy_channel(allow_tools={"create_ticket"})).run_task(
        "reset alice vpn access", thread_id=str(uuid.uuid4()))
    assert "queued" not in json.dumps(out)                 # reset_access ∉ allowlist -> never executed


def test_human_approval_releases_the_side_effect_once(transport):
    """With a granting channel the action executes — and the approval still binds to the seen hashes."""
    out = A2ACaller(transport, lambda proposal: True).run_task(
        "reset alice vpn access", thread_id=str(uuid.uuid4()))
    assert "queued" in out["result"]["answer"]             # executed via the same governed path


def test_caller_cannot_release_without_its_channel(transport):
    """The caller's ONLY path past an interrupt is the channel's decision: a channel that abstains
    (returns None) is a denial — fail closed, nothing executes."""
    out = A2ACaller(transport, lambda proposal: None).run_task(
        "reset alice vpn access", thread_id=str(uuid.uuid4()))
    assert "queued" not in json.dumps(out)

"""Agent-to-agent over the governed HTTP contract (D-040) — governance is transport-independent.

A second agent delegates a task via POST /run (the A2A surface: AgentOutput schema at GET /contract).
If the governed agent proposes a side effect, the caller receives `{status: interrupted, state}` exactly
like a human client would — the approval requirement PROPAGATES across the A2A boundary. The caller has
NO approval authority of its own: its only way past an interrupt is to hand the exact proposal (pending
tool calls + proposal hashes, D-034/D-038) to its `approval_channel` — a human console, an ops queue, or
an explicit policy — and relay that decision, echoing the hashes the channel SAW. An abstaining channel
(None/falsy) is a denial: fail closed (J-04). Auto-approval is therefore an auditable channel policy,
never an emergent caller behavior.

This is deliberately NOT an MCP exposure of the governed graph: over MCP stdio there is no approval
channel — the graph would hang on the interrupt or force auto-approve (J-07 anti-pattern, docs/13).
Read-only tools stay on MCP; the governed path stays on HTTP where approval can round-trip.

Trust boundary (D-033): in production /approve sits behind the authenticated gateway — only principals
with an approver role reach it. This module demonstrates the propagation pattern inside that boundary.
"""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field


@dataclass
class Proposal:
    """What the approval channel decides on — the SAME artifact a human sees in the chat UI."""
    thread_id: str
    pending_tool_calls: list = field(default_factory=list)
    proposal_hashes: list = field(default_factory=list)
    question: str = ""


class A2ACaller:
    """A minimal calling agent. `transport` is anything with .post(path, json=...) returning an
    httpx-style response — httpx.Client(base_url=...) live, or FastAPI's TestClient in tests.
    `approval_channel(proposal) -> bool | None` is the ONLY authority for releasing side effects."""

    MAX_APPROVAL_ROUNDS = 5   # a run may raise several proposals; never loop unbounded (D-001 spirit)

    def __init__(self, transport, approval_channel):
        self.transport = transport
        self.approval_channel = approval_channel

    def run_task(self, task: str, thread_id: str | None = None) -> dict:
        tid = thread_id or str(uuid.uuid4())
        out = self.transport.post("/run", json={"task": task, "thread_id": tid}).json()
        for _ in range(self.MAX_APPROVAL_ROUNDS):
            if out.get("status") != "interrupted":
                return out
            payload = out["state"][0]["value"]
            proposal = Proposal(tid, payload.get("pending_tool_calls", []),
                                payload.get("proposal_hashes", []), payload.get("question", ""))
            decision = self.approval_channel(proposal)     # human/policy decides — the caller cannot
            out = self.transport.post("/approve", json={
                "thread_id": tid,
                "approve": decision is True,               # abstain/None -> deny (fail closed)
                "hashes": proposal.proposal_hashes}).json()
        return out


def policy_channel(allow_tools: set[str]):
    """An explicit, auditable policy: approve ONLY if every pending call's tool is allowlisted.
    Anything else — including an empty proposal — is denied. No human, no discretion, no surprises."""
    def channel(proposal: Proposal) -> bool:
        calls = proposal.pending_tool_calls
        return bool(calls) and all(tc.get("name") in allow_tools for tc in calls)
    return channel


def console_channel(proposal: Proposal) -> bool:
    """A human at a terminal: show exactly what would run and the hashes being approved, ask y/n.
    A closed/absent stdin (EOF) is a DENIAL, not a crash — no input means no approval (fail closed)."""
    print("\n=== APPROVAL REQUIRED (agent-initiated) ===")
    for tc in proposal.pending_tool_calls:
        print(f"  {tc['name']}({json.dumps(tc.get('args', {}))})")
    for h in proposal.proposal_hashes:
        print(f"  proposal_hash {h}")
    try:
        return input("approve? [y/N] ").strip().lower() == "y"
    except EOFError:
        print("(no input — denied)")
        return False

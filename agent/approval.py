"""Approval integrity + idempotency (D-034). An approval must bind to the EXACT proposed action, and an
approved side effect must fire AT MOST ONCE even if the graph is resumed/replayed.

proposal_hash = sha256(tool | normalized_args | principal | tenant | run_id). The human approves THAT hash.
At execution we recompute it from the ACTUAL args being run; if they changed after approval (reset_access
alice → bob), the hash won't match any approved one and execution is REFUSED. LangGraph's interrupt/resume
can replay the tools node, so every executed hash is recorded and a repeat is an idempotent no-op — the side
effect happens exactly once. Read tools carry no side effect, so they need no binding.
"""
from __future__ import annotations
import hashlib
import json


def normalize_args(args: dict | None) -> str:
    """Canonical form so key order / whitespace can't change the hash (or be used to smuggle a change)."""
    return json.dumps(args or {}, sort_keys=True, separators=(",", ":"), default=str)


def proposal_hash(tool: str, args: dict, principal: str, tenant: str, run_id: str) -> str:
    payload = "\x1f".join([str(tool), normalize_args(args), str(principal), str(tenant), str(run_id)])
    return hashlib.sha256(payload.encode()).hexdigest()


def approve_calls(tool_calls, principal: str, tenant: str, run_id: str, needs_approval) -> set[str]:
    """Hashes to authorize when a human approves this proposal — one per side-effecting call."""
    return {proposal_hash(tc["name"], tc.get("args", {}), principal, tenant, run_id)
            for tc in tool_calls if needs_approval(tc["name"])}


def classify_execution(tool_calls, principal: str, tenant: str, run_id: str,
                       approved: set[str], executed: set[str], needs_approval):
    """Per call, decide EXECUTE / REFUSE (unapproved or args changed) / SKIP (already executed). Pure and
    deterministic. Returns (to_execute, refusals[(call, reason)], hashes_to_mark_executed)."""
    to_execute, refusals, mark = [], [], []
    for tc in tool_calls:
        if not needs_approval(tc["name"]):
            to_execute.append(tc)                                    # read tool — no binding
            continue
        h = proposal_hash(tc["name"], tc.get("args", {}), principal, tenant, run_id)
        if h in executed:
            refusals.append((tc, "idempotent skip: this action was already executed"))
        elif h not in approved:
            refusals.append((tc, "REFUSED: action not approved (args changed after approval?)"))
        else:
            to_execute.append(tc)
            mark.append(h)
    return to_execute, refusals, mark

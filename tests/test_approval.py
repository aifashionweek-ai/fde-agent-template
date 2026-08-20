"""D-034 guard: approval binds to the EXACT proposed action (proposal_hash), and an approved action
executes at most once. Catch-proof: approve reset_access(alice) then submit reset_access(bob) with that
approval → REFUSED; replaying an approved action executes once then idempotently skips."""
from agent.approval import proposal_hash, approve_calls, classify_execution

ACTION = {"reset_access", "create_ticket", "provision_resource", "remember", "escalate_to_human"}
def needs_approval(name): return name in ACTION

P, T, R = "alice", "meridian", "run-1"
def call(name, args, cid="c1"): return {"name": name, "args": args, "id": cid}


def test_hash_changes_when_args_change():
    assert proposal_hash("reset_access", {"e": "alice"}, P, T, R) != proposal_hash("reset_access", {"e": "bob"}, P, T, R)


def test_hash_stable_under_key_order():
    assert proposal_hash("t", {"a": 1, "b": 2}, P, T, R) == proposal_hash("t", {"b": 2, "a": 1}, P, T, R)


def test_hash_differs_by_principal_and_tenant_and_run():
    base = proposal_hash("reset_access", {"e": "alice"}, "alice", "meridian", "r1")
    assert base != proposal_hash("reset_access", {"e": "alice"}, "mallory", "meridian", "r1")
    assert base != proposal_hash("reset_access", {"e": "alice"}, "alice", "aristo", "r1")
    assert base != proposal_hash("reset_access", {"e": "alice"}, "alice", "meridian", "r2")


def test_approve_alice_execute_bob_is_refused():
    approved = approve_calls([call("reset_access", {"employee_id": "alice"})], P, T, R, needs_approval)
    to_exec, refusals, mark = classify_execution(
        [call("reset_access", {"employee_id": "bob"})], P, T, R, approved, set(), needs_approval)
    assert to_exec == [] and mark == []
    assert refusals and "REFUSED" in refusals[0][1]


def test_approved_action_executes_once_then_idempotent():
    c = call("reset_access", {"employee_id": "alice"})
    approved = approve_calls([c], P, T, R, needs_approval)
    to_exec, refusals, mark = classify_execution([c], P, T, R, approved, set(), needs_approval)
    assert len(to_exec) == 1 and len(mark) == 1 and not refusals      # first run executes
    to_exec2, refusals2, mark2 = classify_execution([c], P, T, R, approved, set(mark), needs_approval)
    assert to_exec2 == [] and mark2 == [] and "idempotent" in refusals2[0][1]   # replay skips


def test_read_tool_passes_without_binding():
    to_exec, refusals, mark = classify_execution(
        [call("search_policy", {"query": "x"})], P, T, R, set(), set(), needs_approval)
    assert len(to_exec) == 1 and not refusals and not mark


def test_unapproved_action_refused_even_with_empty_approved():
    to_exec, refusals, mark = classify_execution(
        [call("provision_resource", {"resource": "vm"})], P, T, R, set(), set(), needs_approval)
    assert to_exec == [] and refusals and "REFUSED" in refusals[0][1]

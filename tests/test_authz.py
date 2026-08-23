"""D-033 guard: deterministic authorization boundary (agent/authz.py). Catch-proof: every deny-test here
fails if authorize() is neutered to always-allow or a specific check is removed."""
import json
from agent.identity import Principal, principal_from_claims
from agent.authz import authorize, clearance

alice = Principal("alice", "meridian", roles=(), groups=("eng",))
bob = Principal("bob", "meridian")
admin = Principal("carol", "meridian", roles=("helpdesk_admin",))


def test_alice_can_reset_alice():
    assert authorize(alice, "reset_access", {"tenant": "meridian", "subject": "alice"}).allow


def test_alice_cannot_reset_bob():
    d = authorize(alice, "reset_access", {"tenant": "meridian", "subject": "bob"})
    assert not d.allow and "cannot reset" in d.reason


def test_admin_can_reset_others():
    assert authorize(admin, "reset_access", {"tenant": "meridian", "subject": "bob"}).allow


def test_cross_tenant_denied():
    d = authorize(alice, "reset_access", {"tenant": "aristo", "subject": "alice"})
    assert not d.allow and "cross-tenant" in d.reason


def test_self_approval_of_privileged_denied():
    d = authorize(alice, "approve", {"privileged": True, "requester": "alice"})
    assert not d.allow and "self-approval" in d.reason


def test_independent_approver_allowed():
    mgr = Principal("mgr", "meridian", roles=("manager",))
    assert authorize(mgr, "approve", {"privileged": True, "requester": "alice"}).allow


def test_approve_without_role_denied():
    assert not authorize(bob, "approve", {"privileged": True, "requester": "alice"}).allow


def test_retrieve_above_clearance_denied():
    d = authorize(alice, "retrieve", {"sensitivity": "restricted"})
    assert not d.allow and "clearance" in d.reason


def test_retrieve_within_clearance_allowed():
    cleared = Principal("dan", "meridian", roles=("clearance_confidential",))
    assert clearance(cleared) == "confidential"
    assert authorize(cleared, "retrieve", {"sensitivity": "confidential"}).allow


def test_retrieve_doc_acl_group_overlap():
    legal = Principal("erin", "meridian", groups=("legal",))
    assert authorize(legal, "retrieve", {"sensitivity": "internal", "allowed_groups": ["legal"]}).allow
    assert not authorize(alice, "retrieve", {"sensitivity": "internal", "allowed_groups": ["legal"]}).allow


def test_decision_is_falsy_on_deny():
    assert not authorize(alice, "reset_access", {"subject": "bob", "tenant": "meridian"})


def test_principal_from_claims_maps_oidc_keys():
    p = principal_from_claims({"sub": "u1", "tenant": "aristo", "roles": ["approver"], "groups": ["ops"]})
    assert p.user_id == "u1" and p.tenant_id == "aristo" and "approver" in p.roles and "ops" in p.groups


def test_self_approval_bypass_via_identity_variants_is_denied():
    """D-042: the self-approval-of-privileged deny must survive identity spoofing of `requester`.
    A raw string compare let alice self-approve by writing her own name with a trailing space,
    different case, or a full-width homoglyph — normalize (NFKC + casefold + strip) before compare."""
    appr = Principal("alice", "meridian", roles=("approver",))
    for requester in ["alice ", " alice", "ALICE", "Alice", "ａlice"]:   # trailing/leading space, case, full-width 'a'
        d = authorize(appr, "approve", {"privileged": True, "requester": requester})
        assert not d.allow, f"self-approval NOT denied for requester={requester!r}"
        assert "self-approval" in d.reason


def test_reset_self_only_survives_identity_variants():
    """The mirror: reset self-only must not be evadable by casing/whitespace either direction."""
    alice = Principal("alice", "meridian")
    assert authorize(alice, "reset_access", {"tenant": "meridian", "subject": "ALICE"}).allow   # still self
    assert authorize(alice, "reset_access", {"tenant": "meridian", "subject": " alice "}).allow
    assert not authorize(alice, "reset_access", {"tenant": "meridian", "subject": "bob"}).allow  # still not self


def test_tenant_isolation_survives_case_and_whitespace():
    alice = Principal("alice", "meridian")
    assert not authorize(alice, "reset_access", {"tenant": "aristo", "subject": "alice"}).allow
    assert authorize(alice, "reset_access", {"tenant": "MERIDIAN", "subject": "alice"}).allow    # same tenant, cased


def test_reset_access_tool_enforces_authz(monkeypatch):
    from agent.tools import reset_access
    monkeypatch.setenv("USER_ID", "alice"); monkeypatch.setenv("TENANT", "meridian")
    monkeypatch.delenv("ROLES", raising=False)
    denied = json.loads(reset_access.invoke({"employee_id": "bob", "system": "vpn"}))
    assert denied["status"] == "DENIED" and "cannot reset" in denied["reason"]
    allowed = json.loads(reset_access.invoke({"employee_id": "alice", "system": "vpn"}))
    assert allowed["status"] == "queued"


def test_retrieval_enforces_group_acl():
    from agent.retrieval import InMemoryIndex, chunk_document
    idx = InMemoryIndex()
    idx.add(chunk_document("d1", "general VPN access policy for all staff.", source="pol",
                           tenant="meridian", sensitivity="internal"))
    idx.add(chunk_document("d2", "confidential legal VPN memo.", source="legal", tenant="meridian",
                           sensitivity="internal", meta={"allowed_groups": ["legal"]}))
    eng = idx.search("vpn", tenant="meridian", groups={"eng"}, k=10)
    assert any(h["source"] == "pol" for h in eng)
    assert not any(h["source"] == "legal" for h in eng)              # ACL'd doc hidden from non-legal
    leg = idx.search("vpn", tenant="meridian", groups={"legal"}, k=10)
    assert any(h["source"] == "legal" for h in leg)                  # visible to legal

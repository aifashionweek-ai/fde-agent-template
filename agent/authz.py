"""Deterministic authorization (D-033) — the CONTROL plane. authorize(principal, action, resource) returns
an allow/deny Decision computed by pure code, NEVER by the LLM. "Agent proposes, authz disposes, human
approves side effects (HITL)."

Invariants enforced:
  * tenant isolation — a caller acts only within their own tenant (checked first, structural)
  * credential reset — a caller resets only their OWN credentials, unless they hold an admin role
  * approval integrity — no self-approval of a privileged escalation; approver role required
  * retrieval — sensitivity ≤ the caller's clearance AND (no doc ACL, or the caller's groups intersect it)

Every rule is data-driven and testable in isolation (tests/test_authz.py). Removing a check makes a
deny-test fail — that's the catch-proof.
"""
from __future__ import annotations
from dataclasses import dataclass

from .identity import Principal
from .retrieval import SENSITIVITY

ADMIN_ROLES = {"it_admin", "helpdesk_admin"}
APPROVER_ROLES = {"approver", "manager", "it_admin"}
CLEARANCE_BY_ROLE = {"clearance_public": "public", "clearance_internal": "internal",
                     "clearance_confidential": "confidential", "clearance_restricted": "restricted"}


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str
    def __bool__(self) -> bool:      # so `if authorize(...):` works and a deny is falsy
        return self.allow


def _allow(reason: str) -> Decision: return Decision(True, reason)
def _deny(reason: str) -> Decision: return Decision(False, reason)
def _is_admin(p: Principal) -> bool: return bool(ADMIN_ROLES & set(p.roles))


def clearance(p: Principal) -> str:
    """Highest sensitivity the principal may read, derived from clearance_* roles (default 'internal')."""
    levels = [CLEARANCE_BY_ROLE[r] for r in p.roles if r in CLEARANCE_BY_ROLE]
    return max(levels, key=lambda s: SENSITIVITY[s], default="internal")


def authorize(principal: Principal, action: str, resource: dict | None = None) -> Decision:
    r = resource or {}
    # 1) tenant isolation — applies to any action naming a tenant; enforced BEFORE anything else.
    rt = r.get("tenant")
    if rt is not None and rt != principal.tenant_id:
        return _deny(f"cross-tenant denied: principal tenant={principal.tenant_id} != resource tenant={rt}")

    # 2) credential reset — self only, unless an admin role.
    if action == "reset_access":
        subject = r.get("subject")
        if subject is not None and subject != principal.user_id and not _is_admin(principal):
            return _deny(f"{principal.user_id} cannot reset credentials of {subject} (not self, not admin)")
        return _allow("self credential reset" if subject == principal.user_id else "admin credential reset")

    # 3) approval — no self-approval of a privileged escalation; must hold an approver role.
    if action == "approve":
        if r.get("privileged") and r.get("requester") == principal.user_id:
            return _deny("self-approval of a privileged escalation is forbidden")
        if not (APPROVER_ROLES & set(principal.roles) or _is_admin(principal)):
            return _deny(f"{principal.user_id} lacks an approver role")
        return _allow("independent approver")

    # 4) retrieval — clearance ceiling + document group ACL.
    if action == "retrieve":
        sens = r.get("sensitivity", "internal")
        if SENSITIVITY.get(sens, 1) > SENSITIVITY[clearance(principal)]:
            return _deny(f"sensitivity '{sens}' exceeds clearance '{clearance(principal)}'")
        acl = r.get("allowed_groups")
        if acl and not (set(acl) & set(principal.groups)):
            return _deny("document ACL: principal groups do not intersect allowed_groups")
        return _allow("within clearance and document ACL")

    # default: tenant already enforced above; other actions carry no extra authz rule at this layer
    # (side effects are still HITL-gated, and BUILD 2 binds the approval to the exact proposed action).
    return _allow("no additional authz restriction")

# SNIPPET · a deterministic authorize() rule (the CONTROL plane, NEVER the LLM). Two ways to use it.
# ADAPT: pick the resource keys your action carries; return _allow(reason) / _deny(reason).
#
# (A) PREFERRED — add a branch inside agent/authz.py :: authorize(), next to the submit_action branch.
#     It already runs the tenant-isolation check first, so you only add the action-specific rule:
#
#     if action == "do_thing":
#         subject = (resource or {}).get("subject")
#         if subject is not None and not _same(subject, principal.user_id) and not _is_admin(principal):
#             return _deny(f"{principal.user_id} cannot act on {subject} (not self, not admin)")
#         return _allow("self action" if _same(subject, principal.user_id) else "admin action")
#
# (B) STANDALONE — the same rule as a pure function you can unit-test in isolation, then call from (A).
#     Every rule is data-driven and testable; removing a check must make a deny-test go red (catch-proof, J-02).

from agent.authz import Decision
from agent.identity import Principal


def authorize_do_thing(principal: Principal, resource: dict) -> Decision:
    """Self-only unless admin, within tenant. tenant isolation is enforced by authorize() before this."""
    def _same(a, b) -> bool:
        import unicodedata
        norm = lambda s: unicodedata.normalize("NFKC", str(s)).strip().casefold()   # D-042 identity normalize
        return norm(a) == norm(b)

    subject = resource.get("subject")
    is_admin = bool({"admin", "superuser"} & set(principal.roles))
    if subject is not None and not _same(subject, principal.user_id) and not is_admin:
        return Decision(False, f"{principal.user_id} cannot act on {subject} (not self, not admin)")
    return Decision(True, "self action" if _same(subject, principal.user_id) else "admin action")

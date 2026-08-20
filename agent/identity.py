"""Identity — who is making the request (D-031). A Principal carries the caller's tenant, user id, roles
and groups. Authorization decisions (agent/authz.py) are made from the Principal, DETERMINISTICALLY —
never by the LLM.

The claims parser here is a MOCK: it accepts an already-decoded claims dict (as an OIDC/JWT would carry).
PRODUCTION MUST validate a real signed token first — verify the signature against the IdP's JWKS, and
check `iss`, `aud`, and `exp` — before trusting a single claim. Trusting an unverified token is the whole
ballgame; this module assumes that verification happened upstream and only maps claims → Principal.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()

    def as_claims(self) -> dict:
        """Serializable form for AgentState / the trace (state is checkpointed, so store plain data)."""
        return {"user_id": self.user_id, "tenant_id": self.tenant_id,
                "roles": list(self.roles), "groups": list(self.groups)}


def principal_from_claims(claims: dict) -> Principal:
    """Map a DECODED, ALREADY-VERIFIED claims dict to a Principal. Accepts either OIDC-style keys
    (sub/tenant) or plain (user_id/tenant_id). Prod validates the token signature upstream (see module doc)."""
    claims = claims or {}
    return Principal(
        user_id=claims.get("sub") or claims.get("user_id") or "anon",
        tenant_id=claims.get("tenant") or claims.get("tenant_id") or "demo",
        roles=tuple(claims.get("roles") or ()),
        groups=tuple(claims.get("groups") or ()),
    )


def principal_from_env() -> Principal:
    """Demo/eval path: build the Principal from env (USER_ID, TENANT, ROLES, GROUPS as comma lists).
    The same env the tools already read for tenant/user — one source of truth for 'who is calling'."""
    csv = lambda k: tuple(v for v in os.getenv(k, "").split(",") if v)
    return principal_from_claims({
        "user_id": os.getenv("USER_ID", "anon"),
        "tenant_id": os.getenv("TENANT", "demo"),
        "roles": csv("ROLES"),
        "groups": csv("GROUPS"),
    })

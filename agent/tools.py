"""Tool registry — SKELETON (two worked examples, generic).

Read tools are safe (no side effect, no approval). Action tools are side effects -> approval-gated (HITL,
D-004) and authorized deterministically first (D-033). Unknown tool -> needs_approval True (safe default).
Tools return JSON; retrieval ids are the only legal citations.

# SLOT 3: TOOLS — replace these two examples with the domain's tools. KEEP the pattern:
#   - read tools: side_effect:no, approval:no  (safe, tenant/clearance-scoped inside the tool)
#   - action tools: side_effect:YES, approval:YES, and call authorize() BEFORE acting
# How-to: edit the tool table in MASTERSCHEMA.md, implement the @tool fn (name must match the row),
#         then run `python update.py` to regenerate tool_registry.json + drift-check. Never hand-edit it.
"""
from langchain_core.tools import tool
import json, os, pathlib
REGISTRY = {t["name"]: t for t in json.loads((pathlib.Path(__file__).parent / "tool_registry.json").read_text())}


# ---------- READ tool (no side effect, no approval) — worked example ----------
@tool
def search_kb(query: str) -> str:
    """Search the knowledge base for relevant passages. Read-only. Returns chunk ids you MUST cite.
    Scoped to the caller's tenant and clearance automatically.
    # SLOT 3: replace with domain read tools — keep the tenant/clearance scoping."""
    from .retrieval import INDEX, seed_demo
    from .identity import principal_from_env
    if not INDEX.chunks: seed_demo()
    p = principal_from_env()
    groups = set(p.groups) or None                          # D-033: retrieval filtered by the caller's groups
    hits = INDEX.search(query, tenant=p.tenant_id,
                        max_sensitivity=os.getenv("MAX_SENSITIVITY", "internal"), groups=groups, k=5)
    return json.dumps(hits)


# ---------- ACTION tool (side effect -> approval + authz) — worked example ----------
@tool
def submit_action(target: str, detail: str) -> str:
    """Submit an action against a target resource on behalf of an employee. SIDE EFFECT — requires human
    approval (HITL). Authorized deterministically FIRST (D-033/D-045): a caller may act only on their OWN
    target unless they hold an admin role.
    # SLOT 3: replace with domain action tools — KEEP the authorize()-before-acting + approval pattern."""
    from .identity import principal_from_env
    from .authz import authorize
    p = principal_from_env()
    d = authorize(p, "submit_action", {"tenant": p.tenant_id, "subject": target})
    if not d.allow:
        return json.dumps({"action": "submit_action", "status": "DENIED", "reason": d.reason})
    return json.dumps({"action": "submit_action", "target": target, "detail": detail, "status": "queued"})


TOOLS = [search_kb, submit_action]
SIDE_EFFECT_TOOLS = {n for n, t in REGISTRY.items() if t.get("side_effect")}


def tool_needs_approval(name: str) -> bool:
    """Unknown tool -> approval required (safe default in prod). But under STRICT_REGISTRY=1 (tests/CI)
    an unknown tool RAISES, so a registry/parse drift fails loudly instead of hiding as a 'safe default' (J-04)."""
    if name not in REGISTRY:
        if os.getenv("STRICT_REGISTRY") == "1":
            raise KeyError(f"tool '{name}' not in registry — MASTERSCHEMA/registry drift, not a real unknown tool")
        return True
    return REGISTRY[name].get("approval", True)

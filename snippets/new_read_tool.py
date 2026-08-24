# SNIPPET · a new READ tool (copy of search_kb). Paste into agent/tools.py, rename, adjust the body.
# ADAPT: rename `lookup_thing` → your tool; keep it side-effect-free and tenant/clearance-scoped inside.
# THEN: add a row to MASTERSCHEMA.md tool table  ->  | lookup_thing | no | no | 10s |
#       and run `python update.py` to regenerate agent/tool_registry.json (never hand-edit it, J-08).
# Read tools take NO approval and are what MCP publishes automatically (side_effect: no).

from langchain_core.tools import tool


@tool
def lookup_thing(query: str) -> str:
    """One-line description the model sees. Read-only. Returns ids the model MUST cite.
    Scoped to the caller's tenant/clearance automatically."""
    import json

    from agent.identity import principal_from_env
    from agent.retrieval import INDEX, seed_demo

    if not INDEX.chunks:
        seed_demo()                                     # replace with your corpus load (SLOT 2)
    p = principal_from_env()
    groups = set(p.groups) or None                      # tenant/clearance filter BEFORE ranking (J-06)
    hits = INDEX.search(query, tenant=p.tenant_id, max_sensitivity="internal", groups=groups, k=5)
    return json.dumps(hits)                             # ids in the result are the only legal citations

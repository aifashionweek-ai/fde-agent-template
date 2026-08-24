# SNIPPET · a new APPROVAL-GATED ACTION tool (copy of submit_action). Paste into agent/tools.py.
# ADAPT: rename `do_thing` → your action; change the args; keep the authorize()-BEFORE-acting pattern.
# THEN: add a row to MASTERSCHEMA.md tool table  ->  | do_thing | YES | YES | 10s |
#       and run `python update.py` to regenerate the registry. side_effect:YES => it is HITL-gated and is
#       NEVER published over MCP (withheld automatically). The graph routes it through the approval node.
# INVARIANT: authorize() runs FIRST (deterministic, D-033/D-045); a human approves the exact proposal
#            hash SECOND (D-034/D-038). Never let the model authorize or auto-execute a side effect (J-07).

import json

from langchain_core.tools import tool


@tool
def do_thing(target: str, detail: str) -> str:
    """One-line description the model sees. SIDE EFFECT — requires human approval (HITL). Authorized
    deterministically first: a caller may act only on their OWN target unless they hold an admin role."""
    from agent.authz import authorize
    from agent.identity import principal_from_env

    p = principal_from_env()
    d = authorize(p, "do_thing", {"tenant": p.tenant_id, "subject": target})   # add an authz rule (see authz_rule.py)
    if not d.allow:
        return json.dumps({"action": "do_thing", "status": "DENIED", "reason": d.reason})
    # ... perform the real side effect here (call your system of record) ...
    return json.dumps({"action": "do_thing", "target": target, "detail": detail, "status": "queued"})

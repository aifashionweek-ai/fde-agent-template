"""Tool registry — Enterprise IT-Ops / Employee Support agent.
Read tools are safe (no approval). Write/action tools are side effects -> approval-gated (HITL, D-004).
Unknown tool -> needs_approval True (safe default). Tools return JSON; retrieval ids are the only legal citations.

This maps to Hang Ten's "operate software" half: the agent doesn't just answer, it takes real
remediation actions (reset access, file tickets, provision resources) — always human-approved.
"""
from langchain_core.tools import tool
import json, os, pathlib, re
REGISTRY = {t["name"]: t for t in json.loads((pathlib.Path(__file__).parent/"tool_registry.json").read_text())}


# ---------- READ tools (no side effect, no approval) ----------
@tool
def search_policy(query: str) -> str:
    """Search the company's policy wiki and IT runbooks for relevant passages. Read-only.
    Returns chunk ids you MUST cite. Scoped to the caller's tenant and clearance automatically."""
    from .retrieval import INDEX, seed_demo
    if not INDEX.chunks: seed_demo()
    hits = INDEX.search(query, tenant=os.getenv("TENANT", "meridian"),
                        max_sensitivity=os.getenv("MAX_SENSITIVITY", "internal"), k=5)
    return json.dumps(hits)

@tool
def lookup_employee(employee_id: str) -> str:
    """Look up an employee's directory record (name, dept, manager, schedule). Read-only, tenant-scoped."""
    from .directory import lookup
    return json.dumps(lookup(os.getenv("TENANT", "meridian"), employee_id))

@tool
def recall_memory(query: str) -> str:
    """Recall facts remembered about THIS employee from past sessions (preferences, prior tickets). Read-only."""
    from .memory import STORE
    tenant, user = os.getenv("TENANT", "meridian"), os.getenv("USER_ID", "anon")
    mems = STORE.search(tenant, user, query, k=3)
    return json.dumps([{"key": m.key, "value": m.value, "kind": m.kind} for m in mems])

@tool
def calculate(expression: str) -> str:
    """Evaluate a safe arithmetic expression (e.g. PTO days remaining)."""
    import ast, operator as op
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg}
    def ev(n):
        if isinstance(n, ast.Constant): return n.value
        if isinstance(n, ast.BinOp): return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp): return ops[type(n.op)](ev(n.operand))
        raise ValueError("unsafe")
    return str(ev(ast.parse(expression, mode="eval").body))


# ---------- ACTION / side-effect tools (approval required, HITL) ----------
@tool
def reset_access(employee_id: str, system: str) -> str:
    """Reset an employee's access grant for a system (clears lockouts, re-issues SSO token).
    SIDE EFFECT — requires human approval. Never resets OT/SCADA access without change-control."""
    return json.dumps({"action": "reset_access", "employee_id": employee_id, "system": system, "status": "queued"})

@tool
def create_ticket(queue: str, summary: str, priority: str = "P3") -> str:
    """File a ticket to an IT/NetOps/SecOps queue. SIDE EFFECT — requires human approval."""
    return json.dumps({"action": "create_ticket", "queue": queue, "summary": summary,
                       "priority": priority, "ticket_id": "TCK-DEMO-001", "status": "created"})

@tool
def provision_resource(resource: str, employee_id: str) -> str:
    """Provision a resource (license, VM, group membership) for an employee. SIDE EFFECT — requires approval."""
    return json.dumps({"action": "provision_resource", "resource": resource,
                       "employee_id": employee_id, "status": "provisioned"})

@tool
def remember(key: str, value: str) -> str:
    """Persist a durable fact about THIS employee to long-term memory (e.g. schedule, preferences).
    SIDE EFFECT — requires approval. Use for stable facts, not transient chatter."""
    from .memory import STORE
    tenant, user = os.getenv("TENANT", "meridian"), os.getenv("USER_ID", "anon")
    m = STORE.put(tenant, user, "semantic", key, value, source="agent")
    return json.dumps({"ok": True, "id": m.id, "key": key})

@tool
def escalate_to_human(reason: str) -> str:
    """Escalate to a human operator when the task is out of policy or confidence is low. SIDE EFFECT — approval."""
    return json.dumps({"handoff": True, "reason": reason, "queue": os.getenv("HANDOFF_QUEUE", "it-support")})


TOOLS = [search_policy, lookup_employee, recall_memory, calculate,
         reset_access, create_ticket, provision_resource, remember, escalate_to_human]
SIDE_EFFECT_TOOLS = {n for n, t in REGISTRY.items() if t.get("side_effect")}
def tool_needs_approval(name: str) -> bool:
    """Unknown tool -> approval required (safe default in prod). But under STRICT_REGISTRY=1 (tests/CI)
    an unknown tool RAISES, so a registry/parse drift fails loudly instead of hiding as a 'safe default'."""
    if name not in REGISTRY:
        import os
        if os.getenv("STRICT_REGISTRY") == "1":
            raise KeyError(f"tool '{name}' not in registry — MASTERSCHEMA/registry drift, not a real unknown tool")
        return True
    return REGISTRY[name].get("approval", True)

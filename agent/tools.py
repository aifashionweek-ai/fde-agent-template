"""Tool registry. Each tool: a docstring the model reads, a side-effect flag, an approval flag.
Add problem-specific tools here, register in tool_registry.json (or let update.py regen), run update.py.

Design notes for an FDE audience:
  - Read tools (search_kb, calculate, http_get, sql_query, recall_memory) are safe, no approval.
  - Write/side-effect tools (write_record, remember, human_handoff) are gated: tool_needs_approval()
    returns True, the graph routes them through the approval (HITL) node (D-004).
  - Unknown tool name -> needs_approval True by default (safe default).
  - Tools return JSON strings; the agent cites/uses ids from them. Retrieval ids are the only legal citations.
"""
from langchain_core.tools import tool
import json, os, pathlib, re
REGISTRY = {t["name"]: t for t in json.loads((pathlib.Path(__file__).parent/"tool_registry.json").read_text())}


# ---------- READ tools (no side effect, no approval) ----------
@tool
def search_kb(query: str) -> str:
    """Search the customer knowledge base for relevant passages. Read-only. Returns chunk ids you MUST cite."""
    from .retrieval import INDEX, seed_demo
    if not INDEX.chunks: seed_demo()
    hits = INDEX.search(query, tenant=os.getenv("TENANT", "demo"),
                        max_sensitivity=os.getenv("MAX_SENSITIVITY", "internal"), k=5)
    return json.dumps(hits)

@tool
def calculate(expression: str) -> str:
    """Evaluate a safe arithmetic expression (e.g. '17 * 23')."""
    import ast, operator as op
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg}
    def ev(n):
        if isinstance(n, ast.Constant): return n.value
        if isinstance(n, ast.BinOp): return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp): return ops[type(n.op)](ev(n.operand))
        raise ValueError("unsafe")
    return str(ev(ast.parse(expression, mode="eval").body))

@tool
def http_get(url: str) -> str:
    """Fetch a URL (read-only GET). Egress is allow-listed: only hosts in HTTP_ALLOW_HOSTS are permitted."""
    allow = {h.strip() for h in os.getenv("HTTP_ALLOW_HOSTS", "api.github.com,example.com").split(",") if h.strip()}
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if host not in allow:
        return json.dumps({"error": f"host '{host}' not in HTTP_ALLOW_HOSTS", "allowed": sorted(allow)})
    try:
        import requests
        r = requests.get(url, timeout=5)
        return json.dumps({"status": r.status_code, "body": r.text[:2000]})
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def sql_query(query: str) -> str:
    """Run a READ-ONLY SQL query against the analytics DB. SELECT only; writes are rejected before execution.
    Demo backend is an in-memory SQLite with an `orders` table; swap for the customer's warehouse in prod."""
    if not re.match(r"^\s*select\b", query, re.I) or re.search(r"\b(insert|update|delete|drop|alter|create)\b", query, re.I):
        return json.dumps({"error": "read-only: only SELECT permitted"})
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE orders(id int, tenant text, status text, total real)")
    con.executemany("INSERT INTO orders VALUES (?,?,?,?)",
                    [(1, "demo", "shipped", 189.0), (2, "demo", "refunded", 129.5), (3, "acme", "shipped", 42.0)])
    try:
        cur = con.execute(query)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return json.dumps({"rows": rows})
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def recall_memory(query: str) -> str:
    """Recall facts remembered about THIS user from past sessions (long-term/episodic memory). Read-only."""
    from .memory import STORE
    tenant, user = os.getenv("TENANT", "demo"), os.getenv("USER_ID", "anon")
    mems = STORE.search(tenant, user, query, k=3)
    return json.dumps([{"key": m.key, "value": m.value, "kind": m.kind, "age_days": round((__import__("time").time()-m.created_at)/86400, 1)} for m in mems])


# ---------- WRITE / side-effect tools (approval required) ----------
@tool
def write_record(table: str, record: dict) -> str:
    """Write a record to the system of record. SIDE EFFECT — requires human approval."""
    return json.dumps({"ok": True, "table": table, "record": record})

@tool
def remember(key: str, value: str) -> str:
    """Persist a durable fact about THIS user to long-term memory. SIDE EFFECT — requires approval.
    Use for stable preferences/attributes ('prefers_metric', 'tier=enterprise'), not transient chatter."""
    from .memory import STORE
    tenant, user = os.getenv("TENANT", "demo"), os.getenv("USER_ID", "anon")
    m = STORE.put(tenant, user, "semantic", key, value, source="agent")
    return json.dumps({"ok": True, "id": m.id, "key": key})

@tool
def human_handoff(reason: str) -> str:
    """Escalate to a human operator. SIDE EFFECT — requires approval. Use when the task is out of policy
    or the agent's confidence is low on a consequential action."""
    return json.dumps({"handoff": True, "reason": reason, "queue": os.getenv("HANDOFF_QUEUE", "support")})


TOOLS = [search_kb, calculate, http_get, sql_query, recall_memory, write_record, remember, human_handoff]
SIDE_EFFECT_TOOLS = {n for n, t in REGISTRY.items() if t.get("side_effect")}
def tool_needs_approval(name: str) -> bool: return REGISTRY.get(name, {}).get("approval", True)

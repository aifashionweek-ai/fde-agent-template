"""Tool registry. Add problem-specific tools here; register in MASTERSCHEMA then run update.py."""
from langchain_core.tools import tool
import json, pathlib
REGISTRY = {t["name"]: t for t in json.loads((pathlib.Path(__file__).parent/"tool_registry.json").read_text())}

@tool
def search_kb(query: str) -> str:
    """Search the customer knowledge base for relevant passages. Read-only. Returns chunk ids you MUST cite."""
    from .retrieval import INDEX, seed_demo
    import os
    if not INDEX.chunks: seed_demo()
    hits = INDEX.search(query, tenant=os.getenv("TENANT", "demo"),
                        max_sensitivity=os.getenv("MAX_SENSITIVITY", "internal"), k=5)
    return json.dumps(hits)

@tool
def calculate(expression: str) -> str:
    """Evaluate a safe arithmetic expression."""
    import ast, operator as op
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg}
    def ev(n):
        if isinstance(n, ast.Constant): return n.value
        if isinstance(n, ast.BinOp): return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp): return ops[type(n.op)](ev(n.operand))
        raise ValueError("unsafe")
    return str(ev(ast.parse(expression, mode="eval").body))

@tool
def write_record(table: str, record: dict) -> str:
    """Write a record to the system of record. SIDE EFFECT — requires human approval."""
    # TODO: DynamoDB put_item / customer API call
    return json.dumps({"ok": True, "table": table, "record": record})

TOOLS = [search_kb, calculate, write_record]
SIDE_EFFECT_TOOLS = {n for n, t in REGISTRY.items() if t["side_effect"]}
def tool_needs_approval(name: str) -> bool: return REGISTRY.get(name, {}).get("approval", True)

#!/usr/bin/env python
"""MEASURE the 'which is cheaper for a read' claim (D-044) — not assert it (J-02).

Same read query, two paths:
  (a) GOVERNED GRAPH  — full run: guard -> plan -> act(model) -> search_policy -> act(model) -> finalize.
      Real tokens + latency from the telemetry recorder.
  (b) MCP READ TOOL   — the exact tool MCP publishes (search_policy), invoked directly. No model, no
      planning: this is what another agent gets when it calls the read tool over MCP.

Writes evals/fixtures/mcp_vs_graph.json with both measurements and the ratio. The number you quote to a
customer: "for a pure read, the MCP tool is ~Nx cheaper in tokens and ~Mx faster than routing the read
through the whole agent — so expose reads over MCP, keep the governed graph for actions."

  .venv/bin/python scripts/bench_mcp_vs_graph.py      # needs ANTHROPIC_API_KEY for the graph path
"""
import json
import os
import pathlib
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("USER_ID", "alice")
os.environ.setdefault("TENANT", "meridian")

import agent.graph as g
from agent import telemetry
from agent.mcp_server import read_tools
from agent.retrieval import INDEX, chunk_document

OUT = pathlib.Path(__file__).resolve().parent.parent / "evals" / "fixtures" / "mcp_vs_graph.json"
QUERY = "VPN lockout policy: how does an employee restore access?"


def _seed():
    if not any(getattr(c, "doc_id", "") == "vpn-policy" for c in INDEX.chunks):
        INDEX.add(chunk_document("vpn-policy",
            "VPN lockout policy: after 5 failed logins an account locks. An employee restores access by "
            "requesting a reset of their OWN access; cross-user resets need an IT admin.",
            source="policies", tenant="meridian", sensitivity="internal"))


def bench_mcp() -> dict:
    tool = next(t for t in read_tools() if t.name == "search_policy")
    t0 = time.perf_counter()
    tool.invoke({"query": QUERY})                        # the raw read another agent gets over MCP
    ms = round((time.perf_counter() - t0) * 1000, 2)
    return {"path": "mcp_read_tool", "tokens": 0, "latency_ms": ms}   # read tool makes no model call


def bench_graph() -> dict:
    tid = f"bench-{uuid.uuid4().hex[:8]}"
    g.run(f"Call search_policy for the '{QUERY}' and summarize it in one sentence.", thread_id=tid)
    tot = telemetry.last_run(tid)["totals"]
    return {"path": "governed_graph", "tokens": tot["tokens"], "latency_ms": tot["latency_ms"]}


def main():
    _seed()
    mcp, graph = bench_mcp(), bench_graph()
    ratio = {
        "tokens_graph_over_mcp": None if mcp["tokens"] == 0 else round(graph["tokens"] / mcp["tokens"], 1),
        "tokens_saved_by_mcp": graph["tokens"] - mcp["tokens"],
        "latency_graph_over_mcp": round(graph["latency_ms"] / mcp["latency_ms"], 1) if mcp["latency_ms"] else None,
    }
    result = {"query": QUERY, "mcp": mcp, "graph": graph, "ratio": ratio}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\nMCP read tool: {mcp['tokens']} tokens / {mcp['latency_ms']}ms   |   "
          f"graph: {graph['tokens']} tokens / {graph['latency_ms']}ms")
    print(f"=> a pure read over MCP saves {ratio['tokens_saved_by_mcp']} tokens "
          f"and is ~{ratio['latency_graph_over_mcp']}x faster than routing it through the agent.")
    return result


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set — needed for the graph path."); raise SystemExit(1)
    main()

"""MCP server — exposes the agent's READ tools to MCP clients (Claude Desktop, IDEs, other agents).

READ-ONLY BY CONSTRUCTION (J-07). Only no-side-effect tools are published here. The five action tools
(reset_access, create_ticket, provision_resource, remember, escalate_to_human) are side effects and are
NEVER exposed over MCP — they stay behind the agent's HITL approval node. An MCP client physically cannot
trigger a side effect through this server: read_tools() is derived from the tool registry's `side_effect`
flag, and build_server() asserts every published tool is non-side-effecting before it starts. If the
registry ever drifts so an action tool looks read-only, the server refuses to start (fail loud, J-04).

The `mcp` package is an OPTIONAL dependency. Importing this module never requires it, so
`python update.py --check` and the whole test suite run with `mcp` uninstalled. Install only to serve:

    pip install "mcp[cli]"
    python -m agent.mcp_server            # stdio server for Claude Desktop / IDE clients

Why read-only over MCP: MCP hands tools to a client we don't govern (its own model decides when to call).
Reads are safe to delegate — they are tenant/clearance-scoped inside the tool itself. Writes are decisions;
a decision needs the agent's approval node and a human, which an external MCP client bypasses. So writes
never leave the governed graph. (docs/13-mcp-integration.md)
"""
from __future__ import annotations
import json, pathlib

from agent.tools import TOOLS, REGISTRY


def read_tools():
    """The tools safe to publish over MCP: registry side_effect == False (== the no-approval read tools).
    Derived from the registry, not hardcoded — one source of truth (J-08). Importable without `mcp`."""
    safe = []
    for t in TOOLS:
        meta = REGISTRY.get(t.name)
        if meta is None:
            # A tool with no registry row is drift — never publish an unknown tool (safe default, J-07).
            continue
        if not meta.get("side_effect", True):
            safe.append(t)
    return safe


def action_tool_names() -> set[str]:
    """The tools that must NEVER be published (side effects / approval-gated). Used by the guard test."""
    return {t.name for t in TOOLS if REGISTRY.get(t.name, {}).get("side_effect", True)}


def build_server():
    """Construct the FastMCP server with ONLY the read tools registered. Requires `mcp` installed.
    Asserts read-only invariant before returning — a side-effect tool here is a hard startup failure."""
    from mcp.server.fastmcp import FastMCP  # optional dep, imported lazily

    published = read_tools()
    for t in published:
        meta = REGISTRY[t.name]
        assert not meta.get("side_effect", True), \
            f"refusing to publish side-effect tool over MCP: {t.name} (J-07 violation)"
        assert not meta.get("approval", True), \
            f"refusing to publish approval-gated tool over MCP: {t.name} (J-07 violation)"

    server = FastMCP("fde-agent-readonly")

    def register(tool):
        def handler(**kwargs):
            # Delegate to the real, tenant/clearance-scoped tool. Its output is the MCP tool result.
            return tool.invoke(kwargs)
        handler.__name__ = tool.name
        handler.__doc__ = tool.description
        server.add_tool(handler, name=tool.name, description=tool.description)

    for t in published:
        register(t)
    return server


def _print_manifest():
    """No-dep summary of what WOULD be served — runnable without `mcp` for inspection/CI."""
    print(json.dumps({
        "server": "fde-agent-readonly",
        "published_read_tools": [t.name for t in read_tools()],
        "withheld_action_tools": sorted(action_tool_names()),
    }, indent=2))


if __name__ == "__main__":
    import sys
    if "--manifest" in sys.argv:
        _print_manifest()
    else:
        try:
            build_server().run()
        except ImportError:
            print("mcp not installed. `pip install \"mcp[cli]\"` to serve, "
                  "or run `python -m agent.mcp_server --manifest` to see what would be published.")
            raise SystemExit(1)

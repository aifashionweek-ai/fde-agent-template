"""D-025 guard: the MCP server publishes READ tools ONLY. Action/side-effect tools never leave the
governed graph (J-07). Generic invariant, asserted against the skeleton's two example tools —
search_kb (read) is published; submit_action (side effect, approval-gated) is withheld. Catch-proof:
if an action tool were ever classified as read-only, or a read tool marked side-effecting, these fail.
Domain fills add their own read/action tools; this boundary test keeps holding by construction."""
from agent.mcp_server import read_tools, action_tool_names, build_server
from agent.tools import REGISTRY

READ_TOOLS = {"search_kb"}          # side_effect: no, approval: no
ACTION_TOOLS = {"submit_action"}    # side_effect: YES, approval: YES — must stay behind the HITL gate


def test_read_tool_is_published():
    assert READ_TOOLS <= {t.name for t in read_tools()}


def test_no_action_tool_is_published():
    names = {t.name for t in read_tools()}
    assert names.isdisjoint(ACTION_TOOLS)


def test_every_published_tool_is_non_side_effect_and_no_approval():
    # The same invariant build_server() asserts at startup, tested without needing `mcp` installed.
    for t in read_tools():
        meta = REGISTRY[t.name]
        assert meta.get("side_effect") is False
        assert meta.get("approval") is False


def test_action_tools_are_withheld_by_name():
    assert ACTION_TOOLS <= action_tool_names()
    assert action_tool_names().isdisjoint({t.name for t in read_tools()})


def test_import_does_not_require_mcp():
    # Importing the module and enumerating tools must work with `mcp` uninstalled (optional dep).
    import importlib, agent.mcp_server as m
    importlib.reload(m)
    assert callable(m.build_server) and m.read_tools()

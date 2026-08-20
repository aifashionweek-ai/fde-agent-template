"""D-025 guard: the MCP server publishes READ tools ONLY. Action/side-effect tools never leave the
governed graph (J-07). Catch-proof: if an action tool were ever classified as read-only, these fail."""
from agent.mcp_server import read_tools, action_tool_names
from agent.tools import REGISTRY

ACTION_TOOLS = {"reset_access", "create_ticket", "provision_resource", "remember", "escalate_to_human"}
READ_TOOLS = {"search_policy", "lookup_employee", "recall_memory", "calculate"}


def test_only_read_tools_published():
    names = {t.name for t in read_tools()}
    assert names == READ_TOOLS


def test_no_action_tool_is_published():
    names = {t.name for t in read_tools()}
    assert names.isdisjoint(ACTION_TOOLS)


def test_every_published_tool_is_non_side_effect_and_no_approval():
    # The invariant build_server() asserts at startup, tested without needing `mcp` installed.
    for t in read_tools():
        meta = REGISTRY[t.name]
        assert meta.get("side_effect") is False
        assert meta.get("approval") is False


def test_action_tools_are_withheld_by_name():
    assert action_tool_names() == ACTION_TOOLS


def test_import_does_not_require_mcp():
    # Importing the module and enumerating tools must work with `mcp` uninstalled (optional dep).
    import importlib, agent.mcp_server as m
    importlib.reload(m)
    assert callable(m.build_server) and m.read_tools()

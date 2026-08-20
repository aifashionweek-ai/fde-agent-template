# Rule · Tools are registry-driven and HITL-gated (J-07, J-08)

`MASTERSCHEMA.md § Tool registry` is the single source of truth. `agent/tool_registry.json` is DERIVED.

## Adding or changing a tool
1. Edit the tool table in `MASTERSCHEMA.md` (name, side_effect, approval, timeout).
2. Implement/adjust the `@tool` fn in `agent/tools.py` — the fn name must match the row exactly.
3. Run `python update.py` (or `make check`) to regenerate `tool_registry.json` and drift-check.
   - Never hand-edit `tool_registry.json` (J-08). A code/schema mismatch fails the drift check loudly.

## Read vs. action — the boundary
- **Read tools** (`side_effect: no`, `approval: no`): search_policy, lookup_employee, recall_memory,
  calculate. Safe — each is tenant/clearance-scoped inside itself. These are what MCP publishes.
- **Action tools** (`side_effect: YES`, `approval: YES`): reset_access, create_ticket, provision_resource,
  remember, escalate_to_human. Side effects → routed through the HITL approval node. Never auto-execute.
- **Unknown tool → approval by default** (safe). But under `STRICT_REGISTRY=1` (tests/CI) an unknown tool
  RAISES — a registry/parse drift must fail loud, not hide as a "safe default" (J-04).

## MCP exposure
`agent/mcp_server.py` derives its published set from the registry (`side_effect == false`). Adding a read
tool exposes it over MCP automatically; adding an action tool withholds it automatically. `build_server()`
asserts no side-effect / approval-gated tool is ever published, and refuses to boot otherwise. Guarded by
`tests/test_mcp.py` (D-025). See `docs/13-mcp-integration.md`.

## Invariant
An agent that answers is useful; one that ACTS is valuable — but every side effect is human-approved.
"Agent proposes, human disposes." That property is tested (`test_guards.py::test_hitl_gate`), not assumed.

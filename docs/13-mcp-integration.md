# 13 · MCP integration — publishing the agent's read tools

The Model Context Protocol (MCP) lets other clients — Claude Desktop, IDE assistants, other agents —
call this agent's tools directly. We expose **read tools only**. The action tools stay inside the governed
graph, behind the HITL approval node. This is a boundary decision, not a config toggle.

## What's published vs. withheld
| Published over MCP (read, no approval) | Withheld — never leaves the graph (side effect, HITL) |
|---|---|
| `search_policy` | `reset_access` |
| `lookup_employee` | `create_ticket` |
| `recall_memory` | `provision_resource` |
| `calculate` | `remember` |
|  | `escalate_to_human` |

The split is **derived from the tool registry**, not hand-maintained (J-08). `read_tools()` in
`agent/mcp_server.py` returns exactly the tools whose registry row has `side_effect: false`. Add a read
tool to `MASTERSCHEMA.md`, run `python update.py`, and it appears over MCP automatically. Add an action
tool and it is withheld automatically.

## Why read-only (the boundary)
MCP hands a tool to a client we don't govern — the client's own model decides when to call it. That's fine
for **reads**: each read tool is tenant- and clearance-scoped *inside itself*, so it can't return data the
caller isn't entitled to. It is not fine for **writes**: a side effect is a decision, and a decision needs
the agent's approval node plus a human (J-07 — "agent proposes, human disposes"). An external MCP client
would bypass that node, so writes simply aren't offered. `build_server()` asserts the invariant at startup —
if a registry drift ever made an action tool look read-only, the server refuses to boot (fail loud, J-04).

## Running it
`mcp` is an **optional dependency** — `update.py --check` and the test suite run without it.
```bash
pip install "mcp[cli]"
python -m agent.mcp_server              # stdio server for Claude Desktop / IDE clients
python -m agent.mcp_server --manifest   # no-dep: print exactly what would be published/withheld
make mcp                                # == the --manifest inspection
```
Point a client at it (Claude Desktop `claude_desktop_config.json`):
```json
{ "mcpServers": { "fde-agent": { "command": "python", "args": ["-m", "agent.mcp_server"] } } }
```

## The guarantee
The read/write boundary is a tested invariant, not a promise. `tests/test_mcp.py` (D-025) proves the
published set is exactly the four read tools and is disjoint from the five action tools — remove the check
and it goes red. An MCP client can *ask the agent* to do something that needs a side effect, but it cannot
*perform* one: that path always re-enters the graph and stops at the approval node.

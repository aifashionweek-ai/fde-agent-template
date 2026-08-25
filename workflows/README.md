# workflows/

Declarative maps of THIS agent's real flows to the workflow patterns and the controls each step
carries. The framing lives in **[PATTERNS.md](PATTERNS.md)** (workflow-vs-agent, the 5 canonical
patterns, the determination method). Each `*.yaml` is one real flow; nothing is invented (J-01):

- every `node` is a real graph node in `agent/graph.py`,
- every tool is in `agent/tool_registry.json`,
- every control is a `D-###` row in `MANIFEST.md`,
- `pattern` is one of the 5 canonical patterns (or `dynamic-agent`, the agent axis of PATTERNS.md §1).

`tests/test_workflows.py` is the catch-proof: it fails if any workflow names a tool not in the
registry, a control not in the MANIFEST, or an unknown pattern label.

## The workflows
| File | Pattern | Business request | Human gate |
|---|---|---|---|
| [read-answer.yaml](read-answer.yaml) | prompt-chaining | answer a policy/access question from the tenant corpus | none (no side effect) |
| [gated-action.yaml](gated-action.yaml) | evaluator-optimizer *(gate)* | reset access / file a ticket / provision — agent proposes, human disposes | `approval` node |
| [a2a.yaml](a2a.yaml) | prompt-chaining *(across a boundary)* | another agent calls in; the gate still fires | callee `approval`, via the caller's channel |
| [dynamic-react-core.yaml](dynamic-react-core.yaml) | dynamic-agent | the general unknown-path case that the two above wrap | inherited (routes to `approval`) |

## Tools → workflows (which workflows use each tool)
Source: `agent/tool_registry.json` (read = `side_effect:false`, action = `side_effect:true`).

| Tool | Kind | Used by |
|---|---|---|
| `search_policy` | read | read-answer · gated-action · a2a · dynamic-react-core |
| `lookup_employee` | read | read-answer · gated-action · a2a · dynamic-react-core |
| `recall_memory` | read | read-answer · gated-action · a2a · dynamic-react-core |
| `calculate` | read | read-answer · gated-action · a2a · dynamic-react-core |
| `reset_access` | action | gated-action · a2a · dynamic-react-core |
| `create_ticket` | action | gated-action · a2a · dynamic-react-core |
| `provision_resource` | action | gated-action · a2a · dynamic-react-core |
| `remember` | action | gated-action · a2a · dynamic-react-core |
| `escalate_to_human` | action | gated-action · a2a · dynamic-react-core |

Read tools appear in every workflow (each is tenant/clearance-scoped inside itself and needs no
approval). Action tools never appear in **read-answer** — the read path has no side effect — and
everywhere they DO appear they are routed through the `approval` node, never auto-executed (J-07).

## Workflows → tools (which tools each workflow uses)
| Workflow | Read tools | Action tools |
|---|---|---|
| read-answer | search_policy, lookup_employee, recall_memory, calculate | — |
| gated-action | search_policy, lookup_employee, recall_memory, calculate | reset_access, create_ticket, provision_resource, remember, escalate_to_human |
| a2a | search_policy, lookup_employee, recall_memory, calculate | reset_access, create_ticket, provision_resource, remember, escalate_to_human |
| dynamic-react-core | search_policy, lookup_employee, recall_memory, calculate | reset_access, create_ticket, provision_resource, remember, escalate_to_human *(reachable only via approval)* |

## Rendered
`GET /workflows` renders these as a hub stop — leading with the determination method, then each
workflow's step/tool/control sequence and its human-gate point. Served by `api/main.py`.

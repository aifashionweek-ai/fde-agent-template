# snippets/ — paste-and-adapt templates for the 4-slot fill

Copy-paste-ready, domain-agnostic templates that match the **real** skeleton APIs (they import from the
actual modules), so pasting one and adapting it actually works. Each file's top comment has the one-line
"how to adapt". These are illustrative templates — they are **not** imported by the app and not run by the
gate (that's why they can show `do_thing`/`my_layer` placeholders).

| Snippet | What it is | Fill slot |
|---|---|---|
| [`new_read_tool.py`](new_read_tool.py) | a read tool (copy of `search_kb`) — no side effect, no approval, MCP-published | SLOT 3 |
| [`new_action_tool.py`](new_action_tool.py) | an approval-gated action tool (copy of `submit_action`) — `authorize()` first, HITL second | SLOT 3 |
| [`authz_rule.py`](authz_rule.py) | the deterministic `authorize()` rule pattern (branch to add, or standalone testable fn) | SLOT 3 |
| [`eval_cases.jsonl`](eval_cases.jsonl) | one happy/grounding case + one adversarial case, in `dataset.jsonl` shape | SLOT 1 |
| [`telemetry_span.py`](telemetry_span.py) | `@node_span(...)` usage + reading spans back from `/trace` | (frame — reference) |

## The fill loop for a tool (SLOT 3)
1. Copy `new_read_tool.py` or `new_action_tool.py` into `agent/tools.py`; rename + adjust.
2. Add its row to the **MASTERSCHEMA.md** tool table (`name | side_effect | approval | timeout`).
3. Run `python update.py` (or `make check`) to regenerate `agent/tool_registry.json` + drift-check.
   Never hand-edit the registry (J-08). An action tool (`side_effect: YES`) is auto-withheld from MCP and
   auto-routed through the approval node; a read tool (`no`) is auto-published to MCP.

## The fill loop for the golden set (SLOT 1)
Write cases into `evals/dataset.jsonl` (shape in `eval_cases.jsonl`) **first** — it's the spec (J-09).
Row = `{input, expected, tags}`; `tags[0]` is the slice (happy / adversarial / pii / hitl / routing /
grounding / calibration). For per-layer invariants (authz / injection / egress) add rows under
`evals/datasets/<layer>.jsonl` (see the committed examples there for the richer shape).

Adherence to the control invariants (authz-before-gate, approval-hash binding, MCP read-only) is already
tested in `tests/` — your domain tools inherit those guards for free.

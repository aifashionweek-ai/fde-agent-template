# BUILD-ORDER — fill the skeleton in 3 hours

The literal sequence for a fresh engagement. The frame (control plane, eval gate, telemetry, api, MANIFEST
discipline) is already green — you only fill the 4 SLOTs, then wire the demo. Keep `make check` green on
disk at every step (J-02).

| T+ | Step | Do | "Done" looks like |
|---|---|---|---|
| **0:00–0:30** | Read · scope · profile data | Read the brief; write the problem as one `D-0xx` row. If they handed you a data file, run `python -m tools.data_triage <file> --clean` and read `DATA-REPORT.html`. | You can state the real problem in one sentence and you know the data's shape/PII/quirks. |
| **0:30–0:50** | **SLOT 1 · Golden set** | `evals/dataset.jsonl` — write 5–8 cases incl. an adversarial slice (injection / cross-tenant / out-of-policy). Add per-layer rows in `evals/datasets/` if the domain needs new invariants. Templates: **`snippets/eval_cases.jsonl`**. | The golden set encodes the spec; `make evals` runs (may fail — that's the target). |
| **0:50–1:10** | **SLOT 2 · Corpus** | Drop docs in `corpus/`; `load_dir(...)` or edit `seed_demo` with tenant/source/sensitivity. For PDFs/DOCX use `agent/ingest.py`. | `search_kb` returns real citations from the domain corpus, tenant-scoped. |
| **1:10–1:55** | **SLOT 3 · Tools + schema** | Edit the tool table in `MASTERSCHEMA.md`; implement `@tool` fns in `agent/tools.py` (keep read vs action shape + `authorize()` before acting); `python update.py` to regen + drift-check. Copy-paste starters: **`snippets/new_read_tool.py`**, **`snippets/new_action_tool.py`**, **`snippets/authz_rule.py`** (see `snippets/README.md`). | `make check` green with the domain tools; action tools hit the approval gate. |
| **1:55–2:25** | **SLOT 4 · Output contract** | Shape `agent/state.py` `AgentOutput` (typed fields the scorers check) + `agent/prompts.py` system prompt. | The output validates; the graph produces the domain's answer shape. |
| **2:25–2:55** | Red-first bug + wire demo | Pick the one property most worth proving; write a catch-proven test (red → fix → green) as a new `D-###` row. Start the server (`bash demo.sh`), drive `/run` + `/approve` (and `scripts/a2a_demo.py` for A2A). | A real invariant is locked with a test; the chat + approval loop works live. |
| **2:55–3:00** | Freeze + dry-run | `make check` green on disk; tag the freeze; one dry-run of the demo path end to end. | Green gate, clean dry-run, nothing half-built. |

## Rules that don't change
- **Golden set FIRST** (J-09) — the spec before the code.
- **Every `D-###` row has a catch-proven test** (J-02/J-03) — delete the guard, the test goes red.
- **Regenerate `tool_registry.json` via `update.py`** — never hand-edit (J-08).
- **Action tools are authz-checked then human-approved** — `authorize()` before the gate, approval binds to
  the proposal hash. Don't loosen this to move faster.
- **`make check` green on disk** before anything is called done.

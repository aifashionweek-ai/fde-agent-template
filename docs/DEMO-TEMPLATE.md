# DEMO — <problem name> (fill at T+2:40)

**Problem (D-0xx):** <one sentence>.  **Golden rows:** <n> across slices <list>.

**Architecture:** see ARCHITECTURE.md — deployed at `<URL>/run`; model profile `<id>` because <residency/cost reason>.

**Eval table (Braintrust `<project>` · `baseline` → `<vN>`):**
| Scorer | baseline | vN | threshold |
|---|---|---|---|
| schema_valid / tool_allowlist / no_raw_pii / grounded / hitl_respected / path_sane | 1.00 | 1.00 | 1.00 |
| Factuality | | | ≥0.80 |
| rubric_pass | | | ≥0.80 |
| calibration ECE | | | ≤0.15 |
| judge agreement | | | ≥0.80 |

**Guardrails exercised:** injection row refused (L0), PII redacted in/out, `<tool>` interrupted for approval, cross-tenant row returned nothing.

**What I'd do next (in order):** <retrieval change>, <tool>, <open-model slice>, <fine-tune if gate demands>.

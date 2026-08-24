# Model Bake-off — 2026-08-24

**Headline:** NOT all 1.00 — see the table (kept honest). The deterministic controls (schema, PII, grounding, HITL, tenant, budget) run OUTSIDE the model, so they bound worst-case behavior independent of model choice. Every number below is a REAL measured mean over the golden set — skipped models get no column, never a fake.

4 providers (Anthropic · Bedrock · OpenAI · HF) across 2 US vendors (Anthropic, OpenAI) + open weights.

## Deterministic scorers (safety invariants)

| Scorer | Claude Haiku 4.5 (closed/API) | Qwen3-32B (open/Bedrock) | Llama3.3-70B (open/Bedrock) | GPT-4o (closed/API) |
|---|---|---|---|---|
| schema_valid | 1.00 | 1.00 | 1.00 | 1.00 |
| tool_allowlist | 1.00 | 1.00 | 1.00 | 1.00 |
| within_budget | 1.00 | 1.00 | 1.00 | 0.90 |
| injection_refused | 1.00 | 1.00 | 1.00 | 1.00 |
| no_raw_pii | 1.00 | 1.00 | 1.00 | 1.00 |
| grounded | 1.00 | 1.00 | 1.00 | 1.00 |
| hitl_respected | 1.00 | 1.00 | 1.00 | 1.00 |
| path_sane | 1.00 | 1.00 | 1.00 | 1.00 |
| confidence_reported | 1.00 | 1.00 | 1.00 | 1.00 |

### Column provenance (J-01)
- **Claude Haiku 4.5 (closed/API)** — fresh run 2026-08-24
- **Qwen3-32B (open/Bedrock)** — carried from model-eval-2026-08-19.md
- **Llama3.3-70B (open/Bedrock)** — carried from model-eval-2026-08-19.md
- **GPT-4o (closed/API)** — fresh run 2026-08-24

### Skipped this run (no credential — exit 0, not a failure)
- none

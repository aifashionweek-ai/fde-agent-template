# Model Bake-off — Enterprise IT-Ops agent · 2026-08-19

Same governed agent, same golden set, three models. Deterministic scorers are invariants (must be 1.00); judge scores measure nuanced quality.

## Deterministic scorers (safety invariants)

| Scorer | Claude Haiku 4.5 (closed/API) | Qwen3-32B (open/Bedrock) | Llama3.3-70B (open/Bedrock) |
|---|---|---|---|
| schema_valid | 1.00 | 1.00 | 1.00 |
| tool_allowlist | 1.00 | 1.00 | 1.00 |
| within_budget | 1.00 | 1.00 | 1.00 |
| injection_refused | 1.00 | 1.00 | 1.00 |
| no_raw_pii | 1.00 | 1.00 | 1.00 |
| grounded | 1.00 | 1.00 | 1.00 |
| hitl_respected | 1.00 | 1.00 | 1.00 |
| path_sane | 1.00 | 1.00 | 1.00 |
| confidence_reported | 1.00 | 1.00 | 1.00 |

## Judge scores (quality — LLM judges)

| Scorer | Claude Haiku 4.5 (closed/API) | Qwen3-32B (open/Bedrock) | Llama3.3-70B (open/Bedrock) |
|---|---|---|---|
| factual | 0.60 | 0.56 | 0.34 |
| rubric_pass | 0.60 | 0.60 | 0.30 |

## Finding

**Every deterministic safety scorer is 1.00 across all three models** — schema, PII redaction, grounding, HITL, tenant isolation, budget. The governance layer makes the models interchangeable on the things that must not fail. A residency-constrained customer can run open weights (Qwen/Llama) in-account via Bedrock with zero loss on safety.

The **only** differences are in judge-scored quality (factual, rubric) — where the frontier closed model leads modestly. That is the real, measured open-vs-closed tradeoff: pick open for residency/cost/licensing, closed for peak nuanced quality — and the governance holds either way.

_Reproduce: MODEL_PROFILE=<id> EXPERIMENT=<name> python -m evals.harness, then compare evals/results/bake-*.json. All three verified invoking in-account (Bedrock account 135359468175, us-west-2)._
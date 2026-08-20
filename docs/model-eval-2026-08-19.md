# Model Bake-off — Enterprise IT-Ops agent · 2026-08-19

**Headline:** the deterministic *safety controls are model-independent* — schema, PII, grounding, HITL,
tenant isolation, budget all pass 1.00 across Claude, Qwen3, and Llama3.3. On answer *quality* the best
open model (Qwen3-32B) **ties** the closed model (Claude), while the weaker open model (Llama3.3) **visibly
fails** (it emitted raw tool-call JSON as its final answer on several rows). So **model choice here is a
quality decision, not a safety one** — governance holds regardless of which model you run.

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

Judge = a **correctness-focused** rubric (`evals/scorers.make_judges`): a right answer scores full marks
regardless of extra helpful detail, citations are read from the citations field, and a wrong/contradictory
answer still scores 0. (This replaced `autoevals.Factuality`, whose subset/superset scoring capped a
correct-but-verbose answer — e.g. `17 × 23 = 391` vs gold `391` — at 0.60. See D-030.)

| Scorer | Claude Haiku 4.5 (closed/API) | Qwen3-32B (open/Bedrock) | Llama3.3-70B (open/Bedrock) |
|---|---|---|---|
| factual | 1.00 | 1.00 | 0.48 |
| rubric_pass | 0.90 | 0.90 | 0.30 |

## Finding

**Every deterministic safety scorer is 1.00 across all three models** — schema, PII redaction, grounding, HITL, tenant isolation, budget. The governance layer makes the models interchangeable on the things that must not fail. A residency-constrained customer can run open weights (Qwen/Llama) in-account via Bedrock with zero loss on safety.

The differences are in judge-scored quality. With the corrected judge, **Claude (closed) and Qwen3-32B (open) tie at factual 1.00 / rubric 0.90** — a residency-bound customer loses nothing on nuanced quality by running Qwen open-weights in-account. **Llama3.3-70B is genuinely weaker (0.48 / 0.30)**: on several rows it emitted a raw tool-call JSON blob as its final answer instead of completing the ReAct loop, which the judge correctly scores 0 (a real failure, not a rubric artifact — the fix still fails wrong answers). That is the real, measured open-vs-closed picture: the best open model matches closed on this task; a weaker open model does not — and the governance holds for all three either way.

_Reproduce: MODEL_PROFILE=<id> EXPERIMENT=<name> python -m evals.harness, then compare evals/results/bake-*.json. All three verified invoking in-account (Bedrock account 135359468175, us-west-2)._
# 14 · Safety, tracing & infra — how the non-negotiables fit together

Three cross-cutting concerns hold the agent together in production: **safety** (nothing unsafe egresses),
**tracing** (you can see everything it did), and **infra** (it runs where the customer's data-residency
rules allow). This doc is the map; each has a deep-dive (docs/04, 06, 02/07).

## Safety — 6 layers, deterministic-first
Governance is layered so the cheap, testable checks run first and models are only trusted where they must be
(J-06). Full detail: [docs/04-guardrails.md](04-guardrails.md); contract in `MASTERSCHEMA.md § Guard layers`.

| Layer | What | When | Deterministic? |
|---|---|---|---|
| L0 | regex PII/injection, budget, allowlist, schema | always | yes |
| L1 | Presidio PII | `GUARD_PII=presidio` | yes |
| L2 | Prompt-Guard / Lakera injection classifier | `GUARD_INJECTION=…` | model |
| L3 | Bedrock Guardrails (in-band) | `BEDROCK_GUARDRAIL_ID` | model |
| L4 | output grounding + **egress** PII scrub | `GROUNDING_MIN` | yes |
| L5 | human approval on side effects (HITL) | tool registry `approval` | human |

Two rules that are easy to get wrong:
- **Egress PII runs on EVERY output path, including fallback/error branches** (J-06). A leak once hid in the
  `finalize` fallback; there's now a test for it.
- **Attach a Bedrock Guardrail only with a real id.** An invalid `guardrailIdentifier` 400s the entire
  Converse call — this once broke a whole model bake-off (every open-model tool row failed) until the trace
  showed it was config, not the model. `agent/models.py::_bedrock_guardrail()` skips a missing/placeholder id
  cleanly rather than poisoning the call (J-04). This is why D-022's original "Qwen tool-calling fails"
  finding was **wrong** — it was the guardrail id, and Qwen3-32B tool-calls fine on Bedrock.

## Tracing — the path is the evidence
LangSmith traces every run with `tenant`, `model_profile`, `git_sha`, `experiment` metadata, and the node
**PATH** (including tool names) is carried in the output itself and scored (`path_sane`, D-013). App-level
events use structlog JSON with full, untruncated error text (J-12) — when something fails you read the log,
you don't theorize. Deep-dive: [docs/06-tracing-langsmith.md](06-tracing-langsmith.md).

Why both: LangSmith is the agent trace (prompts, tool I/O, tokens, path — and prod traces become new eval
rows); structlog is the application log (guard decisions, model builds, errors). One shows the reasoning,
the other shows the plumbing.

## Infra — run where residency allows
The same graph deploys three ways; the choice is driven by where the customer's data must stay.

| Path | Where it runs | Residency | Reference |
|---|---|---|---|
| Anthropic API | vendor | `vendor_api` | default; direct key |
| **Bedrock** (closed + open weights) | customer AWS account/VPC | `customer_vpc` | [docs/02-bedrock.md](02-bedrock.md) |
| HF endpoint / TGI / vLLM | self-hosted GPU | `self_hosted` | [docs/07-huggingface-deploy.md](07-huggingface-deploy.md) |
| AWS Lambda + SAM | serverless API host | follows model path | `deploy/` (`make deploy`) |

For regulated customers (healthcare/energy), retrieval store, warehouse, memory, **and** inference all live
inside the customer boundary — open weights on Bedrock in-account (Qwen3/Llama3.3) mean no data leaves the
VPC while safety scorers stay 1.00 (see [docs/model-eval-2026-08-19.md](model-eval-2026-08-19.md) and
[docs/12-data-platforms.md](12-data-platforms.md)).

## The through-line
Safety is deterministic where it can be and human where it must be; tracing makes every decision auditable;
infra lets the same governed agent run inside the customer's compliance boundary. None of the three is a
prompt — each is a tested invariant wired into the graph.

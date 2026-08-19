# MASTERSCHEMA — canonical contracts (source of truth; update.py regenerates derived files)

## AgentState (agent/state.py)
| Field         | Type                | Notes                                  |
|---------------|---------------------|----------------------------------------|
| messages      | list[BaseMessage]   | append-only, LangGraph add_messages    |
| task          | str                 | user goal (guarded input)              |
| plan          | list[str]           | planner output                         |
| step_count    | int                 | incremented per node; D-001            |
| tool_calls    | int                 | budget tracking; D-007                 |
| result        | AgentOutput | None  | schema-validated final; D-002          |
| needs_approval| bool                | HITL flag; D-004                       |
| errors        | list[str]           | guard rejections, tool failures        |
| path          | list[str]           | node sequence; D-013                   |

## AgentOutput (agent/state.py) — the contract the eval judges against
| Field       | Type        | Validation                                        |
|-------------|-------------|---------------------------------------------------|
| answer      | str         | non-empty, <= 4000 chars, PII-redacted on egress  |
| confidence  | float       | 0.0–1.0; capped 0.5 if partially grounded, 0.7 if no evidence (D-012) |
| citations   | list[str]   | ⊆ retrieved chunk ids (docid#n); D-012            |
| actions     | list[Action]| each action ∈ tool allowlist; D-003               |
| trace       | dict        | {path, steps, tool_calls} — added by run(); D-013 |

## Tool registry (agent/tools.py)
| Tool            | Side effect | Approval | Timeout |
|-----------------|-------------|----------|---------|
| search_kb       | no          | no       | 10s     |
| calculate       | no          | no       | 2s      |
| write_record    | YES         | YES      | 10s     |
| http_get        | no          | no       | 6s      |
| sql_query       | no          | no       | 6s      |
| recall_memory   | no          | no       | 3s      |
| remember        | YES         | YES      | 5s      |
| human_handoff   | YES         | YES      | 5s      |

## Memory (agent/memory.py) — three kinds
| Kind | Scope | Lifetime | Backend | Row |
|------|-------|----------|---------|-----|
| short-term / working | thread_id | one thread (checkpointed) | LangGraph checkpointer | — |
| long-term / semantic | (tenant, user) | across sessions | Store (JSON demo / Postgres / vector) | D-016 |
| episodic | (tenant, user) | across sessions | same Store, kind=episodic | D-016 |
Isolation is structural (tenant+user filter before ranking); provenance + TTL on every item; forget() deletes by key or scope (D-017). Writes are approval-gated (D-018).

## Model registry (agent/models.py) — tiers come from YOUR evals, not vendor claims
| Profile               | Provider  | Weights | Residency    | Cost | Latency | Quality | Good for |
|-----------------------|-----------|---------|--------------|------|---------|---------|----------|
| claude-sonnet-api     | anthropic | closed  | vendor_api   | 3    | 2       | 5       | reasoning, extraction, summarization, codegen |
| claude-haiku-api      | anthropic | closed  | vendor_api   | 1    | 1       | 3       | classification, extraction |
| claude-sonnet-bedrock | bedrock   | closed  | customer_vpc | 3    | 2       | 5       | reasoning, extraction, summarization, codegen |
| llama-3.1-70b-bedrock | bedrock   | open    | customer_vpc | 2    | 3       | 4       | summarization, classification, extraction |
| llama-3.1-8b-hf       | hf        | open    | self_hosted  | 1    | 2       | 2       | classification, extraction |
| qwen2.5-7b-hf         | hf        | open    | self_hosted  | 1    | 2       | 2       | classification, extraction, codegen |
Selection order (D-009): hard constraints (residency, cost ≤, quality ≥, task ∈ good_for) → prefer_open → quality desc → cost asc → latency asc. `MODEL_PROFILE` env overrides.

## Retrieval routing (agent/retrieval.py)
| Dimension     | Enforcement                                   | Row   |
|---------------|-----------------------------------------------|-------|
| tenant        | filter BEFORE scoring; never a soft boost     | D-011 |
| sensitivity   | public < internal < confidential < restricted; request ceiling | D-011 |
| source        | optional allow-list of source names           | D-011 |
| provenance    | doc_id, chunk_id, source, tenant, sensitivity, ingested_at on every chunk | D-010 |
| scoring       | BM25 always; + cosine on embeddings if EMBED_PROVIDER set (hybrid 50/50) | — |
| citations     | only returned chunk ids are legal citations   | D-012 |

## Guard layers (agent/guards.py)
| Layer | What                                   | Switch                              | Cost   |
|-------|----------------------------------------|-------------------------------------|--------|
| L0    | regex PII/injection, budgets, allowlist, schema | always on                   | ms     |
| L1    | Presidio PII                           | GUARD_PII=presidio                  | ms     |
| L2    | Prompt-Guard / Lakera injection classifier | GUARD_INJECTION=promptguard|lakera | 10s ms |
| L3    | Bedrock Guardrails (in-band)           | BEDROCK_GUARDRAIL_ID                | in-band|
| L4    | output grounding + egress PII          | GROUNDING_MIN (0..1)                | ms     |
| L5    | human approval on side effects         | tool registry `approval`            | human  |

## Eval dataset row (evals/dataset.jsonl)
| Field     | Type | Notes                                                       |
|-----------|------|-------------------------------------------------------------|
| input     | str  | task                                                        |
| expected  | str  | gold answer or rubric (rubrics must be decidable by a judge) |
| tags      | list | first tag = slice: happy / adversarial / pii / hitl / routing / grounding / calibration |

## Scorers (evals/scorers.py) — Braintrust; gate.py enforces
LLM-judge scorers run through the Braintrust AI proxy: add an Anthropic or OpenAI key under Braintrust → Settings → AI Providers (once per org).
| Scorer            | Type          | Threshold |
|-------------------|---------------|-----------|
| schema_valid      | deterministic | 1.00      |
| tool_allowlist    | deterministic | 1.00      |
| within_budget     | deterministic | 1.00      |
| injection_refused | deterministic | 1.00      |
| no_raw_pii        | deterministic | 1.00      |
| grounded          | deterministic | 1.00      |
| hitl_respected    | deterministic | 1.00      |
| path_sane         | deterministic | 1.00      |
| confidence_reported | deterministic | 1.00    |
| Factuality        | LLM-judge     | >= 0.80   |
| rubric_pass       | LLM-judge     | >= 0.80   |
| calibration_ECE   | meta          | <= 0.15   |
| judge_agreement   | meta          | >= 0.80   |
| slice_regression  | meta          | <= 0.05   |

## Tracing metadata (agent/tracing.py) — every LangSmith run
| Key            | Source                         |
|----------------|--------------------------------|
| tenant         | run(tenant=…) or TENANT env    |
| model_profile  | MODEL_PROFILE / LLM_PROVIDER   |
| git_sha        | git rev-parse                  |
| experiment     | EXPERIMENT env (live by default)|
| tags           | tenant:<t>, model:<p>          |

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

## Tool registry (agent/tools.py) — SLOT 3: replace with domain tools (keep read vs action shape)
| Tool          | Side effect | Approval | Timeout |
|---------------|-------------|----------|---------|
| search_kb     | no          | no       | 10s     |
| submit_action | YES         | YES      | 10s     |

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
| group ACL     | no `allowed_groups` = open; else needs ∩ caller groups; no-groups caller sees only open docs | D-036 |
| backend parity| in-memory `_group_ok` and Pinecone filter make the SAME access decision across the matrix (open / right-group / wrong-group / no-groups / cross-tenant). Pinecone: `add()` upserts `allowed_groups`; `search()` filters `$exists:false OR $in` — never a bare `$in` | D-037 |

## Identity & authorization (agent/identity.py, agent/authz.py) — the CONTROL plane
| Piece | What | Notes |
|-------|------|-------|
| Principal | user_id, tenant_id, roles, groups | parsed from verified OIDC/JWT claims upstream; into AgentState (D-033) |
| authorize(principal, action, resource) | DETERMINISTIC allow/deny — never the LLM | tenant isolation · self-only reset (unless admin) · no self-approval of privileged · retrieve ≤ clearance ∧ group ACL |
| identity comparison (D-042) | NFKC + strip + casefold before compare (`_norm`) | case/whitespace/compat-homoglyph variants can't slip a deny; cross-script confusables (Cyrillic) are a documented residual |
| enforcement | tools call authorize() before acting; retrieval filters by `groups` | trust boundary: gateway authenticates, this layer enforces per-principal |
| ordering (D-045) | authz runs BEFORE the approval gate (in the approval node) AND inside the tool (defense-in-depth) | a human is never shown an unauthorizable proposal; unauthorized proposal rejected pre-interrupt |

## Approval integrity (agent/approval.py) — D-034
| Piece | What |
|-------|------|
| proposal_hash | sha256(tool \| normalized_args \| principal \| tenant \| run_id) — the human approves THIS hash |
| bind | at execution, recompute from actual args; not-in-approved ⇒ REFUSED (args changed after approval) |
| idempotency | each executed hash recorded; replay/resume ⇒ idempotent skip (side effect fires once) |
| wire protocol (D-038) | interrupt payload = `{pending_tool_calls, proposal_hashes, question}`; `/approve` = `{thread_id, approve, hashes}` — approval grants the hashes the human SAW, never what is pending at resume time; a proposal mutated after being shown is REFUSED at execution. `/approve` may return another `interrupted` (further/changed proposal), never a 500. A new run on a reused thread clears the stale `result` |
| enforced in | graph `approval` node records approved hashes; `traced_tools` classifies EXECUTE/REFUSE/SKIP |

## Interfaces (api/main.py) — how anything talks to the agent
| Route | What | Notes |
|-------|------|-------|
| `POST /run` | `{task, thread_id?, tenant?}` → result+trace, or `{status: interrupted, state}`; on a thread with an undecided approval → `{status: pending_approval, state}` (same proposal — decide it first, D-041) | tenant field is TRACE-only; the enforcement principal is env/gateway (D-033 trust boundary). Multi-turn: reuse thread_id; system prompt + memory ctx are bound at the model call, never persisted (exactly one system message per call, D-041) |
| errors | ANY unexpected exception → `500 {error, thread_id, detail}` JSON — never a plain-text 500 (D-041) | full traceback to server log (J-12); chat client parses defensively (no blind `r.json()`) |
| `POST /approve` | `{thread_id, approve, hashes}` → result+trace, or another `interrupted` | hashes = what the human SAW (D-038); never 500s on a follow-up interrupt |
| `GET /` | chat UI (`api/chat.html`, D-039) | static HTML+fetch, no framework; renders pending_tool_calls + proposal_hashes + trace path; approve echoes the SEEN hashes |
| `GET /health` · `GET /contract` | liveness · AgentOutput JSON schema | /contract is the A2A contract surface |
| `GET /trace/{thread_id}` | last run's per-layer spans + totals (D-044) | tokens/latency/cost per node; for the dashboard |
| `GET /dashboard` · `GET /fixtures/runs` · `GET /fixtures/mcp` | observability UI + captured offline demo data (D-044) | dashboard renders spans; fixtures let the demo run without live model calls |

## Telemetry spans (agent/telemetry.py) — D-044, observability only
| Field | What | Notes |
|-------|------|-------|
| layer, kind | node name · MODEL\|CODE | plan/act = MODEL; guard_input/tools/approval_gate/finalize = CODE |
| tokens_in/out | REAL provider usage_metadata via RecordingLLM proxy | CODE layers = 0; totals sum to run tokens (not estimated) |
| latency_ms, cost_usd | measured per span; cost at configurable rate | COST_PER_1M_INPUT / COST_PER_1M_OUTPUT env |
| status | PASS \| GATED \| DENIED \| REFUSED \| SWAYED | GATED=interrupt; DENIED=authz; REFUSED=hash unbound/replay; SWAYED=action denied after untrusted retrieval (D-043) |
| tools[] | per side-effect: redacted args, result, proposal_hash, recomputed_hash, hash_match | makes the D-034 binding visible; args PII-redacted, principal never emitted |
MCP (`agent/mcp_server.py`) publishes READ tools only (D-025) — the governed graph is NEVER exposed over MCP (no approval channel over stdio).
A2A (`agent/a2a.py`, D-040): a calling agent uses `POST /run`; interrupts propagate — release requires its `approval_channel` (human/policy) echoing the seen hashes; abstain = deny.

## Ingestion (agent/ingest.py) — the stage before retrieval
| Step | What | Notes |
|------|------|-------|
| parse | `unstructured.partition.auto.partition` (REAL, optional dep) | auto-detects PDF/DOCX/HTML/PPTX/images; `fast`=pdfminer (default), `hi_res`=layout+poppler |
| clean | drop Header/Footer/PageBreak/PageNumber elements; `ftfy` encoding fix; strip blank/page-number lines | real cleaning, not a no-op |
| chunk | `chunk_document()` — SAME as seed/load_dir | identical tenant/sensitivity provenance tagging |
| tag  | meta: path, content_hash (sha256[:16]), elements, parser | dedup/lifecycle hooks (D-033 extends with ACLs) |
| skip | corrupt/empty/unsupported → logged + counted, never raises | `ingest_directory` returns real counts (files, chunks, bytes) |
Optional extras in requirements-ingest.txt; core + `update.py --check` run without them (D-032).

**Lifecycle + document ACLs (D-036).** Chunk meta also carries `source_id, document_id, document_version,
content_hash, source_uri, allowed_groups, UNTRUSTED`. `sync_document()` is content-hash driven —
unchanged→skip, new→add, modified→replace (re-chunk + delete old), identical-content-elsewhere→dedup;
`delete_document()` removes a deleted source's vectors. Retrieval authorization = **tenant AND
sensitivity≤clearance AND allowed_groups ∩ principal.groups**. Retrieved content is UNTRUSTED (an
indirect-injection surface): it is data, never instructions — only tools + authz can act.

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

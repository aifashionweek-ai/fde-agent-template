# FDE Agent Template — a governed, observable, deployable LangGraph agent

> **Demo domain: Enterprise IT-Ops & Employee Support** — an internal agent that answers employees' access / VPN / HR / finance questions from tenant-scoped runbooks *and takes real remediation actions* (reset access, file tickets, provision resources) under human approval. Two tenant enterprises (Meridian Health, Aristo Energy) and four sensitivity tiers demonstrate multi-tenant isolation and clearance ceilings. Swap the corpus + tools for any customer domain; the governance is unchanged.

> Built for forward-deployed work: drop a production-grade agent into a customer's environment in hours, with the guardrails, evals, tracing and data-routing that make it *safe to leave running*. Every rule is a tested invariant; the deploy refuses to pass if one regresses.

[![check](https://img.shields.io/badge/update.py%20--check-58%20tests%20green-brightgreen)]() [![license](https://img.shields.io/badge/license-MIT-blue)]()

## What you get
| Layer | What's in the box | Why it matters to a customer |
|---|---|---|
| **Agent** | LangGraph `guard_input → plan → act ⇄ tools → [approval] → finalize`, typed state, hard termination | bounded, resumable, human-in-the-loop on anything with a blast radius |
| **Model** | registry + constraint-driven `select_model` (Anthropic API · **Bedrock**, incl. serverless open weights: DeepSeek, Qwen3, Kimi, Ministral, gpt-oss · **Hugging Face** endpoints) + `scripts/model_bakeoff.sh` | *shortlist on Hugging Face, serve on Bedrock, decide with Braintrust* — residency/license/cost decide *can we*; your evals decide *is it good* |
| **Memory** | three kinds: short-term (checkpointed thread), long-term semantic + episodic (`agent/memory.py`, tenant+user scoped, injected before planning, approval-gated writes) | agents that remember safely across sessions — structurally isolated, forgettable |
| **Data** | routed retrieval: provenance on every chunk, **tenant isolation + sensitivity ceiling before scoring**, hybrid BM25+embeddings, citations only from retrieved ids | multi-tenant RAG that can't leak by construction |
| **Guardrails** | 6 layers: regex → Presidio → Prompt-Guard/Lakera → Bedrock Guardrails → output grounding + egress PII → human | deterministic where possible, judged where necessary, humans on the residual |
| **Evals** | Braintrust: deterministic invariants at 1.0, two LLM judges with agreement, **calibration (ECE)**, per-slice regression **gate** | "the evals passed" means something |
| **Tracing** | LangSmith with tenant/model/sha metadata; every result carries its **node path** | traces become eval rows; prod closes the loop |
| **Governance** | `MANIFEST.md` (D-rows) ↔ `tests/` ↔ `MASTERSCHEMA.md` ↔ `update.py --check --evals` (drift + tests + gate) | a directive that isn't a test is a defect |
| **Deploy** | SAM → Lambda (Secrets Manager key or Bedrock IAM) · Docker → App Runner · HF Inference Endpoint script · Bedrock preflight | curl a public URL in minutes |

## 60-second start
```bash
make setup                 # deps + .env
make check                 # update.py: regenerate registry, drift checks, 58 catch-proven tests
make run                   # http://localhost:8080/docs  → POST /run {"task":"I am locked out of the analytics dashboard, can you help?","tenant":"meridian"}
EXPERIMENT=baseline make evals && make gate EXP=baseline
scripts/model_bakeoff.sh claude-sonnet-api claude-haiku-api deepseek-v3.2-bedrock   # one command, one table
```
Works with no keys for `make check`. Add `ANTHROPIC_API_KEY` (or run `make preflight` for Bedrock) for `/run` and evals.

## Audit report — the walkthrough artifact
`make audit` reads the latest eval results, a live pytest run, the MANIFEST, and git, and writes `evals/results/AUDIT.html`: a 7-layer drill-down (guardrails, retrieval, memory, tools/HITL, model selection, tracing, evals) where each layer shows **what it does, why this choice, the alternatives, and the real evidence**. The verdict is computed from logs, not asserted — a failing layer shows red. It's the artifact you screen-share to walk through the whole agent.

## The 3-hour build clock (interview / first customer day)
| T+ | Do | Output |
|---|---|---|
| 0:00 | Write the problem as one **D-0xx** row + 3–5 golden rows per slice | scope locked |
| 0:15 | `AgentOutput` for this problem (MASTERSCHEMA → `state.py`); real tools in `tools.py`; `python update.py` | contract |
| 0:45 | `load_dir(...)` their docs with tenant/source/sensitivity; `make run`; first LangSmith trace | data flowing |
| 1:15 | `make evals` baseline → failures by slice → one change → `EXPERIMENT=v2` → `make gate EXP=v2 BASE=baseline` | numbers |
| 2:00 | `tests/test_problem.py` for the D-0xx guard; `make check` green | proof |
| 2:20 | `make deploy` (or Docker) → curl the URL | live |
| 2:40 | `docs/DEMO-TEMPLATE.md` → DEMO.md | story |

## Playbooks (read these — they're the point)
| | |
|---|---|
| [01 · Model selection](docs/01-model-selection.md) | open vs closed weights, the four constraints, filling quality tiers from *your* evals |
| [02 · Bedrock](docs/02-bedrock.md) | when it earns its place, the enablement gates, Guardrails, `scripts/bedrock_preflight.sh` |
| [03 · Retrieval & customer data](docs/03-retrieval-and-customer-data.md) | where documents land, routing before ranking, store choices, PII/residency/retention |
| [04 · Guardrails](docs/04-guardrails.md) | which tool at which layer (Presidio, Prompt Guard, Lakera, Bedrock Guardrails, NeMo), testing rails |
| [05 · Evals with Braintrust](docs/05-evals-braintrust.md) | golden sets, scorer design, **how to trust a judge** (agreement, calibration), the tuning loop, dataset from prod |
| [06 · Tracing with LangSmith](docs/06-tracing-langsmith.md) | reading a trace, path capture, dashboards/alerts, Langfuse for self-hosted |
| [07 · Deploying open weights](docs/07-huggingface-deploy.md) | HF Inference Endpoints vs TGI/vLLM vs SageMaker vs Bedrock; sizing; gotchas |
| [08 · Tuning](docs/08-tuning.md) | the ladder (prompt → retrieval → tools → model → fine-tune), one change per experiment, drift |
| [09 · FDE playbook](docs/09-fde-playbook.md) | discovery → shadow → HITL ramp → rollout gates → what you leave behind |
| [10 · Agentic memory](docs/10-agentic-memory.md) | the three memory kinds, how each is implemented, memory-as-customer-data, scaling |
| [11 · Fine-tuning open weights](docs/11-finetuning-open-weights.md) | LoRA/QLoRA with HF PEFT, where training runs (SageMaker/residency), Bedrock Custom Model Import, the runnable scaffold |
| [Architecture](docs/ARCHITECTURE.md) | diagram + request/data/model/governance paths |

## Governance in one picture
```
MANIFEST.md  D-001…D-015 + D-0xx ──each row──▶ tests/ (catch-proven: delete the guard, the test fails)
MASTERSCHEMA.md  contracts · tool registry · model registry · routing · guard layers · scorer thresholds
update.py        regenerates tool_registry.json · drift checks · pytest · [--evals] Braintrust gate
```
`python update.py --check` exits non-zero on: a tool in code missing from the schema, a D-row whose test file doesn't exist, any failing test, or (with `--evals`) any deterministic scorer < 1.0, judged scorer < threshold, ECE > 0.15, judge agreement < 0.80, or a slice regressing > 0.05.

## Repository structure
```
.
├── agent/           # the LangGraph agent — graph, guards, tools, memory, models, retrieval, MCP server
├── api/             # FastAPI surface (/run · /approve · /health · /contract)
├── evals/           # golden set (dataset.jsonl), harness, gate, + audit & problem HTML reports
├── deploy/          # ship it — Dockerfile, SAM template.yaml, hf_endpoint.py (open weights)
├── scripts/         # bedrock preflight · model bake-off · new-engagement verify · loom demo driver
├── docs/            # the numbered layer playbooks (01–14) + model-eval + Loom script
├── tests/           # one catch-proven guard per MANIFEST directive
├── .claude/         # rules for Claude Code (evals, tools, debugging conventions)
├── CLAUDE.md        # how an AI agent navigates this repo (commands, architecture, J-01…J-12)
├── MANIFEST.md      # D-### directives — each one ↔ a test
├── MASTERSCHEMA.md  # canonical contracts (state, tools, models, routing, scorers)
└── update.py        # regenerates derived files, drift-checks, runs the gate
```

## Scale & limitations — what's demo-scale vs production-grade
Stated up front, because knowing the boundary is a credibility feature, not a disclaimer. The demo runs
zero-setup; each backend swaps behind the same contract, callers unchanged — so scale is a config change,
not a rewrite.

| | Demo default (this repo) | Production (same interface) |
|---|---|---|
| Retrieval store | in-memory BM25 | `VECTOR_BACKEND=pinecone` — one namespace per tenant (docs/12) |
| Corpus | small seeded set (single-digit docs, by design) | `load_dir()` / ingestion over object storage (S3) — hundreds→millions |
| Golden set | a few rows per slice | hundreds of rows, grown from prod traces |
| Model | Anthropic API | Bedrock **in-account** for residency, or HF endpoint — swap via `MODEL_PROFILE` |
| API host | local `uvicorn` | AWS Lambda (SAM) / App Runner (Docker) — graph is stateless, scales horizontally |
| Memory | JSON file | Postgres / DynamoDB (docs/12) |

**Production-grade already** (not demo-scale): the contracts, the 6-layer guardrails, HITL, tenant +
sensitivity routing, tracing, the eval gate, and the MANIFEST→test governance. These don't change with scale.
**Demo-scale by design**: corpus size and the in-memory index — swapped by env, no code change. The point of
the template is that the *governance* is production-grade on day one; the *data plane* grows into the customer's.

## Document ingestion — real, not a demo stub
`agent/ingest.py` parses real enterprise documents with **Unstructured.io** (Apache-2.0, the library
production RAG teams use): `partition()` auto-detects PDF/DOCX/HTML/PPTX/images → strip header/footer
boilerplate → `ftfy` clean → the same `chunk_document()` provenance tagging as the rest of the pipeline.
**Verified on real PDFs** — 3 public NIST documents → 615 retrievable chunks; see
[docs/INGESTION-PROOF.md](docs/INGESTION-PROOF.md) for the actual output. Optional install (kept out of
core so `update.py --check` runs without it): `pip install -r requirements-ingest.txt` (+ `brew install
poppler` for the hi_res strategy). Without it the core runs fine and ingestion raises a clear, actionable error.

## The one-paragraph pitch
It's a LangGraph agent behind a FastAPI endpoint. Every request passes a layered input guard, gets planned, then runs a bounded plan-act loop against an allowlisted tool set (search, calculate, http_get, sql_query, recall_memory, write_record, remember, human_handoff), pausing for human approval on side effects. Retrieval is routed — tenant, sensitivity, source — before anything is ranked, and only retrieved ids can be cited; the output is schema-validated and grounding-checked before it leaves. The model is a profile chosen by constraints — Anthropic by default, Bedrock when traffic must stay in the customer's account, open weights on Hugging Face when a narrow task or residency demands it. Every run is traced in LangSmith with its path and tenant, and scored in Braintrust against a golden set with calibration and judge-agreement checks; a regression gate blocks the deploy. It's governed by a MANIFEST of directives, a MASTERSCHEMA of contracts, and an `update.py` that refuses to pass unless the guards do.

---
MIT · built by [Jaswant Tawdekar](https://github.com/jaswanttawdekar) — the same governance pattern runs the production platform at aifashionweek.ai.

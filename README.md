# FDE Agent Template — a governed, observable, deployable LangGraph agent

> Built for forward-deployed work: drop a production-grade agent into a customer's environment in hours, with the guardrails, evals, tracing and data-routing that make it *safe to leave running*. Every rule is a tested invariant; the deploy refuses to pass if one regresses.

[![check](https://img.shields.io/badge/update.py%20--check-29%20tests%20green-brightgreen)]() [![license](https://img.shields.io/badge/license-MIT-blue)]()

## What you get
| Layer | What's in the box | Why it matters to a customer |
|---|---|---|
| **Agent** | LangGraph `guard_input → plan → act ⇄ tools → [approval] → finalize`, typed state, hard termination | bounded, resumable, human-in-the-loop on anything with a blast radius |
| **Model** | registry + constraint-driven `select_model` (Anthropic API · **Bedrock** in-VPC · **Hugging Face** open weights) | residency/license/cost decide *can we*; your evals decide *is it good* |
| **Data** | routed retrieval: provenance on every chunk, **tenant isolation + sensitivity ceiling before scoring**, hybrid BM25+embeddings, citations only from retrieved ids | multi-tenant RAG that can't leak by construction |
| **Guardrails** | 6 layers: regex → Presidio → Prompt-Guard/Lakera → Bedrock Guardrails → output grounding + egress PII → human | deterministic where possible, judged where necessary, humans on the residual |
| **Evals** | Braintrust: deterministic invariants at 1.0, two LLM judges with agreement, **calibration (ECE)**, per-slice regression **gate** | "the evals passed" means something |
| **Tracing** | LangSmith with tenant/model/sha metadata; every result carries its **node path** | traces become eval rows; prod closes the loop |
| **Governance** | `MANIFEST.md` (D-rows) ↔ `tests/` ↔ `MASTERSCHEMA.md` ↔ `update.py --check --evals` (drift + tests + gate) | a directive that isn't a test is a defect |
| **Deploy** | SAM → Lambda (Secrets Manager key or Bedrock IAM) · Docker → App Runner · HF Inference Endpoint script · Bedrock preflight | curl a public URL in minutes |

## 60-second start
```bash
make setup                 # deps + .env
make check                 # update.py: regenerate registry, drift checks, 29 catch-proven tests
make run                   # http://localhost:8080/docs  → POST /run {"task":"Summarize the refund policy","tenant":"demo"}
EXPERIMENT=baseline make evals && make gate EXP=baseline
```
Works with no keys for `make check`. Add `ANTHROPIC_API_KEY` (or run `make preflight` for Bedrock) for `/run` and evals.

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
| [Architecture](docs/ARCHITECTURE.md) | diagram + request/data/model/governance paths |

## Governance in one picture
```
MANIFEST.md  D-001…D-015 + D-0xx ──each row──▶ tests/ (catch-proven: delete the guard, the test fails)
MASTERSCHEMA.md  contracts · tool registry · model registry · routing · guard layers · scorer thresholds
update.py        regenerates tool_registry.json · drift checks · pytest · [--evals] Braintrust gate
```
`python update.py --check` exits non-zero on: a tool in code missing from the schema, a D-row whose test file doesn't exist, any failing test, or (with `--evals`) any deterministic scorer < 1.0, judged scorer < threshold, ECE > 0.15, judge agreement < 0.80, or a slice regressing > 0.05.

## Layout
```
agent/   graph.py · state.py · tools.py · guards.py · models.py · retrieval.py · tracing.py · multi.py (A2A supervisor) · prompts.py
api/     main.py (FastAPI + Mangum; /run /approve /health /contract)
evals/   dataset.jsonl · scorers.py · run_evals.py · gate.py
tests/   test_guards.py · test_retrieval.py · test_models.py · test_evals_meta.py
deploy/  template.yaml (SAM) · Dockerfile · hf_endpoint.py
scripts/ bedrock_preflight.sh · smoke.sh
docs/    01–09 playbooks · ARCHITECTURE.md · DEMO-TEMPLATE.md
```

## The one-paragraph pitch
It's a LangGraph agent behind a FastAPI endpoint. Every request passes a layered input guard, gets planned, then runs a bounded plan-act loop against an allowlisted tool set, pausing for human approval on side effects. Retrieval is routed — tenant, sensitivity, source — before anything is ranked, and only retrieved ids can be cited; the output is schema-validated and grounding-checked before it leaves. The model is a profile chosen by constraints — Anthropic by default, Bedrock when traffic must stay in the customer's account, open weights on Hugging Face when a narrow task or residency demands it. Every run is traced in LangSmith with its path and tenant, and scored in Braintrust against a golden set with calibration and judge-agreement checks; a regression gate blocks the deploy. It's governed by a MANIFEST of directives, a MASTERSCHEMA of contracts, and an `update.py` that refuses to pass unless the guards do.

---
MIT · built by [Jaswant Tawdekar](https://github.com/jaswanttawdekar) — the same governance pattern runs the production platform at aifashionweek.ai.

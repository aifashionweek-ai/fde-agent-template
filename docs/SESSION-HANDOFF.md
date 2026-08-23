# SESSION HANDOFF — read this one file to get oriented

A governed, observable, deployable **LangGraph agent** for forward-deployed work. Demo domain: Enterprise
IT-Ops & Employee Support. The point isn't the domain — it's that every safety/quality property is a
**tested invariant**, and a new engagement is done by filling **4 slots** (see §5). This doc makes a fresh
session as oriented as the one that built it.

Ground truth to trust: `git log`, `MANIFEST.md`, and `python update.py --check`. Don't infer state — run it.

---

## 1. Architecture — four planes over one graph

Runtime graph (`agent/graph.py`):
```
guard_input → plan → act ⇄ tools → [approval / HITL] → finalize
```
- **guard_input** — PII scrub + prompt-injection check + memory recall; builds the `Principal` (§2).
- **plan** — LLM drafts steps.
- **act ⇄ tools** — ReAct loop; side-effect tools route through **approval** first.
- **approval** — HITL interrupt; records the approved proposal hashes (§2). `DEMO_AUTOAPPROVE=1` auto-passes for demos.
- **finalize** — schema-validate (`AgentOutput`) + grounding check + egress PII scrub.

Every node appends to `path`; the result carries `{path, steps, tool_calls}`, traced in LangSmith.

**Four planes** are a lens over the audit report's 10 layers (L1–L10) + security D-rows:

| Plane | Owns | Layers / D-rows |
|---|---|---|
| **Intelligence** | getting the answer right | model registry (L5) · routed RAG (L2) · 3-kind memory (L3) · plan→act |
| **Control** | bounding what it can *do* | guardrails (L1) · tools+HITL (L4) · identity+authz (**D-033**) · approval integrity (**D-034**) · tenant/sensitivity/doc-ACL (**D-036**) |
| **Assurance** | proving it continuously | tracing (L6) · eval gate (L7) · adversarial suite (**D-035**) · audit report (D-029) · MANIFEST→test |
| **Integration** | fitting the customer's stack | MCP (L8, D-025) · swappable vector backend (L9, D-024) · infra/deploy (L10) · ingestion (**D-032/036**) |

Control + Assurance are the FDE differentiators — most demos ship only Intelligence + Integration.

The audit report (`evals/audit_report.py`, `make audit`) renders all 10 layers with what/why/alternatives/
evidence, verdict computed from a live pytest run + git. `make problem` renders the business-problem breakdown.

---

## 2. Control plane — the specifics that matter

**Identity + authorization (D-033, `agent/identity.py` + `agent/authz.py`)**
- `Principal(user_id, tenant_id, roles, groups)` parsed from OIDC/JWT claims. The parser is a MOCK; prod
  validates a real signed token upstream (verify sig/iss/aud/exp). Trust boundary: an authenticated gateway
  hands in the principal; this repo enforces *inside* that boundary.
- `authorize(principal, action, resource) → Decision` is **deterministic code, never the LLM.** Enforces:
  tenant isolation; self-only credential reset (unless an admin role); no self-approval of a privileged
  escalation; retrieval clearance ceiling + document group-ACL.

**Approval integrity + idempotency (D-034, `agent/approval.py`)**
- `proposal_hash = sha256(tool | normalized_args | principal | tenant | run_id)`. The human approves *that
  hash*; at execution the hash is recomputed from the ACTUAL args and **REFUSES on mismatch** (approve
  `reset_access(alice)` / execute `reset_access(bob)` → REFUSED).
- Each executed hash is recorded, so a LangGraph interrupt/resume **replay executes the side effect once**.
- Wired in the graph: `approval` node records approved hashes; `traced_tools` classifies each call
  EXECUTE / REFUSE / idempotent-SKIP.

**Tenant isolation** — *structural*, not a soft boost: retrieval filters tenant (and sensitivity, and
source, and group ACL) **before scoring** (`agent/retrieval.py`, D-011); `authorize()` denies cross-tenant;
the Pinecone backend uses one namespace per tenant.

**ACLs** — retrieval authorization = **tenant AND sensitivity ≤ clearance AND allowed_groups ∩
principal.groups** (D-036). Doc-level `allowed_groups` lives in chunk metadata; a doc with no `allowed_groups`
is open (tenant + sensitivity still apply).

---

## 3. Test state

- **160 passing, 0 warnings** (full local run). NOTE: D-044 observability lives on branch
  `feat/observability-evals` (off tag `freeze-pre-observability`), not yet merged to main — main is at 153.
  Recent adds: D-037 ACL-parity, D-038 HITL-wire,
  D-039 chat UI, D-040 A2A, D-041 multi-turn/errors (turn-2 system-prompt-persist 500 → bound at the model
  call), **D-042 identity normalization** (self-approval deny-bypass via case/whitespace/homoglyph — real
  control bypass, fixed), **D-043 indirect-injection-through-retrieval** (poisoned doc obeyed by a swayed
  model, gate+authz still hold — the flagship proof). Red-team posture in `docs/HARDENING-BACKLOG.md`.
  `python update.py --check` is the gate: regenerates
  `agent/tool_registry.json` from `MASTERSCHEMA.md`, drift-checks, runs pytest.
- **CI: two jobs, both green on `7254df3`** (`.github/workflows/check.yml`):
  - `check-core` — `requirements.txt` only → **112 passed, 2 skipped** (the 2 ingestion test modules
    `importorskip` `unstructured`; proves a clean clone works + optional deps degrade gracefully).
  - `check-full` — `+ requirements-ingest.txt` + poppler, `OMP_NUM_THREADS=1` → **122 passed** (ingestion
    tests actually execute the real Unstructured parser).
- **43 MANIFEST rows.** ⚠️ Numbering has a gap: **D-031 does not exist** — the rows are **D-001…D-030,
  D-032…D-043, D-0xx**. Harmless (`update.py` doesn't require contiguity), but don't hunt for D-031.
  `D-0xx` is the intentional problem-specific slot (open). Every other row has a catch-proven guard.

---

## 4. What I'd improve before the next coding exercise (honest)

1. ~~**Pinecone group-ACL gap.**~~ **FIXED (D-037, 2026-08-22).** The Pinecone branch had TWO divergences
   from in-memory `_group_ok`: the bare `allowed_groups: {$in: [...]}` filter excluded open docs (no ACL
   field), AND `add()` never upserted `allowed_groups` / no filter was applied for a no-groups caller —
   a leak, not just over-restriction. Proven red-first against a filter-evaluating fake Pinecone; now
   `$exists:false OR $in` + ACL upserted. Guard: `tests/test_retrieval_backend.py::test_acl_decision_parity_with_in_memory`
   asserts both backends make the SAME access decision across the matrix. MANIFEST row D-037 (37 rows now, 125 tests).
2. ~~**No graph-level integration test.**~~ **FIXED (D-038, 2026-08-22).** `tests/test_api_hitl.py` drives
   the REAL graph through the REAL FastAPI surface (TestClient, only the LLM scripted): /run → interrupted →
   /approve → executes once → replay → idempotent skip → deny → nothing. Red-first, it caught two real
   wiring bugs: (a) the wire protocol had NO binding — /approve approved whatever was pending at resume
   time, so a state-tampered proposal (alice→bob) executed on the human's approval; now the interrupt
   payload carries `proposal_hashes` and /approve `{approve, hashes}` grants only what the human SAW.
   (b) a reused thread replayed the stale `result` instead of running the new task — `run()` now clears it.
3. **Trust boundary is assumed, not implemented** — no real IdP/token-signature verification (documented as
   such). Fine for the artifact; be ready to explain the boundary crisply.
4. **LangSmith is observability, not a durable compliance audit log.** A regulated deployment needs an
   append-only, retained record of who-approved-what-when — a separate store, not a tracing dashboard.
5. **`datetime.utcnow()` deprecation warnings** (evals reports) — cosmetic; swap to timezone-aware for a
   clean run.

(Already acknowledged as roadmap, not gaps: rate limits/quotas, cost caps beyond `budget_guard`, HA/DR,
canary, secrets/KMS. The 4-tier sensitivity model is a simplification of real per-doc/per-group ACLs.)

---

## 5. Reusability — a new domain = fill 4 slots, everything else untouched

1. **Golden set** — `evals/dataset.jsonl` (incl. adversarial rows). **Write this FIRST — it's the spec.**
2. **Corpus** — `agent/retrieval.py` seed / `load_dir()`, or `agent/ingest.py` for real documents.
3. **Tools** — `agent/tools.py` (+ the `MASTERSCHEMA.md` tool table, then `python update.py`).
4. **Output contract** — `agent/state.py` `AgentOutput` + `agent/prompts.py` (system prompt).

Everything else (graph, guards, memory, tracing, eval gate, authz, approval integrity, governance) stays
untouched. `python scripts/verify_new_engagement.py` proves the 4-slot swap still holds.

---

## 6. File-level orientation

**Governance (the spine)**
- `MANIFEST.md` — every directive is a `D-###` row → a catch-proven test. A directive that isn't a test is a defect.
- `MASTERSCHEMA.md` — canonical contracts (state, output, tool registry, model registry, routing, guard layers, scorer thresholds, memory, identity/authz, approval, ingestion). **Single source of truth.**
- `update.py` — regenerates `agent/tool_registry.json` from MASTERSCHEMA, drift-checks, runs pytest. `--check` is the gate.
- `CLAUDE.md` — working conventions (J-01…J-12). `jaswant-manifest.md` (gitignored) — the private engineering canon.

**Agent core (`agent/`)**
- `graph.py` — the LangGraph wiring + `run()`. `state.py` — `AgentState`, `AgentOutput`, `Action`.
- `prompts.py` — system + planner prompts (output contract). `llm.py` — provider-agnostic LLM getter.
- `models.py` — model registry + deterministic `select_model(task, residency, cost, quality, license)`.
- `retrieval.py` — `InMemoryIndex` + `PineconeIndex` behind one `search()` contract; tenant/sensitivity/source/group routing before scoring; `chunk_document`.
- `guards.py` — 6-layer guardrails (regex/Presidio PII, injection, grounding, egress PII, budgets).
- `memory.py` — 3-kind memory (short-term, semantic, episodic), tenant+user scoped, approval-gated writes.
- `tracing.py` — LangSmith metadata + node path. `logging_setup.py` — structlog. `multi.py` — A2A supervisor.

**Control-plane modules (`agent/`)**
- `identity.py` (D-033) — `Principal`, claims parsing. `authz.py` (D-033) — deterministic `authorize()`.
- `approval.py` (D-034) — `proposal_hash`, `approve_calls`, `classify_execution`.
- `ingest.py` (D-032/036) — real Unstructured.io parsing → `chunk_document`; content-hash lifecycle
  (skip/add/replace/dedup/delete); doc ACLs; optional dep (imported lazily).
- `mcp_server.py` (D-025) — publishes READ tools only; action tools stay behind HITL.

**API + deploy** — `api/main.py` (FastAPI: `/` chat UI · `/run` · `/approve` `{approve, hashes}` D-038 ·
`/health` · `/contract`). `api/chat.html` (D-039: static governance-visible chat — proposal + hashes +
approve/deny + trace path, no framework). `agent/a2a.py` + `scripts/a2a_demo.py` (D-040: calling agent —
interrupts propagate, release only via approval_channel). `deploy/` (Dockerfile, SAM `template.yaml`, `hf_endpoint.py`).

**Evals + reports (`evals/`)**
- `dataset.jsonl` (golden set) · `scorers.py` (deterministic + LLM judges; `make_judges` correctness rubric, D-030) · `harness.py` (writes `results/*.json`) · `gate.py` (offline threshold gate) · `run_evals.py` (Braintrust push) · `rescore.py` (re-score captured bake outputs).
- `audit_report.py` (D-029, 10-layer HTML) · `problem_report.py` (D-026, business-problem HTML). Reports render to `evals/results/*.html` (gitignored).

**Tests (`tests/`)** — one guard per D-row: `test_guards, test_retrieval, test_models, test_memory,
test_evals_meta, test_mcp, test_problem_report, test_retrieval_backend, test_loom, test_audit_report,
test_scorers_judge, test_authz, test_approval, test_ingest, test_ingest_lifecycle`.
- `tests/adversarial/` — `test_attacks.py` (~21 red-team cases, `pytest tests/adversarial`),
  `test_model_difference.py` (real Llama-vs-Claude divergence; falls back to committed
  `fixtures/bakeoff_sample.json` so it runs in CI).

**Scripts** — `verify_new_engagement.py` (4-slot proof) · `model_bakeoff.sh` · `loom_demo.sh` (5-beat demo)
· `bedrock_preflight.sh` · `smoke.sh`. **Docs** — numbered playbooks `01`–`14`, `model-eval-2026-08-19.md`,
`INGESTION-PROOF.md`, `LOOM-SCRIPT.md`, `ARCHITECTURE.md`, `img/` (Proof screenshots).

**Data** — `data/sample_corpus/` (3 real public NIST PDFs → 615 chunks; see `INGESTION-PROOF.md`).

---

**First commands in a fresh session:** `python update.py --check` (gate) · `make audit` / `make problem`
(reports) · `git log --oneline -15` · read `MANIFEST.md`.

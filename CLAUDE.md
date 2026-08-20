# CLAUDE.md — working guide for this repo

A governed, observable, deployable **LangGraph agent** for forward-deployed work. Demo domain: Enterprise
IT-Ops & Employee Support. The point of the repo is not the domain — it's that every safety/quality property
is a **tested invariant**, and any new engagement is done by filling **4 slots**, leaving everything else
untouched.

## Prime directives (from jaswant-manifest.md — read it first)
These are defects when violated, not style choices. The full canon (with lessons) is in
`jaswant-manifest.md` (gitignored — local only). The ones that shape every change here:

- **J-01 · No guessing — run through logs.** Every claim about state comes from a real file, live command,
  or log. If you can't cite evidence, say "NO EVIDENCE" and go get it.
- **J-02 · No false greens.** A verdict is computed from results, never asserted. A check that can pass while
  the thing is broken is itself the top bug. Prove a guard fails when what it guards is removed (catch-proof).
- **J-03 · Atomic numbering.** Every directive = a `D-###` row in `MANIFEST.md` + a `MASTERSCHEMA.md` contract
  + a catch-proven test, in the **same** session. A directive that lives only in chat is a defect.
- **J-04 · Fail loud, not safe-silent.** Under strict/CI mode, drift RAISES. A gate that "fails safe" by
  silently over-restricting still hides a defect (see `STRICT_REGISTRY`, `_bedrock_guardrail()`).
- **J-06 · Security is STRUCTURAL.** Tenant/clearance isolation is a filter applied BEFORE ranking. Egress
  PII redaction runs on EVERY output path, including fallbacks.
- **J-07 · Side effects need a human.** Any tool that writes/acts is approval-gated (HITL). Unknown tool →
  approval by default. This is why MCP publishes read tools only (`agent/mcp_server.py`).
- **J-08 · One source of truth per fact.** Derived files (e.g. `agent/tool_registry.json`) are REGENERATED
  from `MASTERSCHEMA.md` by `update.py` — never hand-edit them.
- **J-09 · Evals are the spec.** Golden set (incl. adversarial) written BEFORE code. Deterministic scorers at
  1.0 are invariants; judges are thresholded and measured against each other. Never pass on missing rows.
- **J-10 · Cheapest rung first.** prompt → retrieval → tools → model swap → fine-tune. Move a rung only when
  the previous plateaus on the evals.
- **J-12 · Structured logging, always.** Model calls, guard decisions, tool calls, errors emit structlog JSON
  with full, untruncated context. The log is the evidence — read it, don't theorize.

## Architecture (what fires, in order)
```
guard_input (PII scrub + injection + memory recall)
  → plan → act ⇄ tools (ReAct)
  → [approval / HITL on side effects]
  → finalize (schema-validate + grounding + egress PII scrub)
```
Every node appends to `path`; the result carries `{path, steps, tool_calls}`. Traced in LangSmith, scored in
Braintrust. See `docs/ARCHITECTURE.md` and `docs/14-safety-tracing-infra.md`.

## Key files
| Area | File | Notes |
|---|---|---|
| Graph | `agent/graph.py` | node wiring; `run()` |
| State/contract | `agent/state.py` | `AgentState`, `AgentOutput` (the eval contract) |
| Model registry | `agent/models.py` | `select_model(task, residency, cost, quality, license)` — deterministic |
| Retrieval | `agent/retrieval.py` | provenance + tenant/sensitivity/source filters BEFORE scoring |
| Guards | `agent/guards.py` | 6 layers (docs/04) |
| Memory | `agent/memory.py` | 3 kinds, tenant+user scoped, approval-gated writes |
| Tools | `agent/tools.py` + `tool_registry.json` | read (no approval) vs action (HITL) |
| MCP | `agent/mcp_server.py` | publishes READ tools only (docs/13) |
| Evals | `evals/harness.py` · `evals/gate.py` | harness writes `results/*.json`; gate enforces OFFLINE |
| Reports | `evals/audit_report.py` · `evals/problem_report.py` | HTML from real evidence |
| Governance | `MANIFEST.md` · `MASTERSCHEMA.md` · `update.py` | directives ↔ contracts ↔ guards |

## Commands
```bash
make check       # python update.py --check — regen registry + drift checks + pytest (the gate)
make audit       # evals/audit_report.py — multilayer audit HTML from real evidence
make problem     # evals/problem_report.py — business-problem breakdown HTML
make mcp         # agent/mcp_server.py --manifest — show what MCP would publish/withhold
make evals       # run_evals.py (pushes to Braintrust)
make run         # uvicorn api.main:app
python scripts/verify_new_engagement.py   # prove the 4-slot swap still works
```
`make check` is the gate. It must be green **on disk** before anything is called done (J-02).

## The 4 slots (any new engagement changes only these)
1. `evals/dataset.jsonl` — golden set incl. adversarial rows. **Write first — it's the spec.**
2. `agent/retrieval.py` seed / load — their corpus, scoped.
3. `agent/tools.py` (+ `MASTERSCHEMA.md` tool table, then `update.py`) — their read + action tools.
4. `agent/state.py` `AgentOutput` + `agent/prompts.py` — output contract + system prompt.
Everything else (graph, guards, memory, tracing, eval gate, governance) stays untouched.

## Boundaries — do NOT
- Hand-edit `agent/tool_registry.json` — regenerate via `update.py` (J-08).
- Mark a `D-###` row ✅ unless its guard exists and passes on disk (J-02). No asserted greens.
- Add a directive without a `MANIFEST` row + `MASTERSCHEMA` contract + catch-proven test (J-03).
- Publish a side-effect tool over MCP, or execute one without the approval node (J-07).
- Commit secrets — they live only in local `.env` (gitignored). `jaswant-manifest.md` is gitignored (private).
- Detailed rules live in `.claude/rules/{evals,tools,debugging}.md`.

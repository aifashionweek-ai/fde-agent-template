# CARRY-IN BRIEF

> The one file a fresh session (or Jaswant) reads at the start of a **new problem** to be fully oriented.
> Not the coding guide (that's `CLAUDE.md`) — this is the *orientation*. Everything below is grounded in
> real repo state (J-01). Last-verified baseline is dated in §9.

---

## 1 · THE THESIS
The model reasons flexibly; everything that **must not go wrong** — authorization, tenant isolation,
approvals on side effects, prompt-injection containment — is enforced in **deterministic code OUTSIDE the
model**, and each control has a **catch-proven test** (delete the guard → a test goes red). The model can be
swapped (Claude, Qwen3, Llama3.3, GPT-4o — see §8); the boundary doesn't move. *The model can change; the
boundary doesn't.*

## 2 · THE J-RULES (the two that gate everything)
- **J-01 — Measure real state, don't assume.** Every claim comes from a real file, a live command, or a log.
  No evidence → say "NO EVIDENCE" and go get it.
- **J-02 — Never fake a green, never fabricate a number.** A verdict is *computed* from results, never
  asserted. A check that can pass while the thing is broken is itself the top bug. (Full canon: local
  `jaswant-manifest.md`, gitignored.)

## 3 · THE 6 GOVERNANCE PROPERTIES (the reusable template)
These carry to **any** domain. The golden set (SLOT 1) re-instantiates them for the new corpus/tools.

| # | Property | Enforced by | Catch-proven test / D-row |
|---|---|---|---|
| 1 | **read → answered** | routed retrieval + grounding (citations ⊆ retrieved ids) | `D-011` · `agent/retrieval.py`, `agent/graph.py` finalize |
| 2 | **authorized action → gated** | HITL approval node; agent proposes, human disposes | `D-025`/HITL · `agent/graph.py` approval |
| 3 | **unauthorized → denied pre-gate** | deterministic `authorize()` (tenant/clearance) *before* ranking | `D-033` · `agent/authz.py` (`test_alice_cannot_reset_bob`) |
| 4 | **tamper → refused (hash binding)** | `proposal_hash(tool+args+principal+tenant+run_id)`; recompute at exec, refuse if changed | `D-034` · `agent/approval.py` (`test_approve_alice_execute_bob_is_refused`) |
| 5 | **injection → contained** | 6-layer input guard; retrieved text is data, not instructions | `D-035` · `agent/guards.py` (`test_direct_injection_is_refused`) |
| 6 | **a2a → gate propagates** | HITL interrupt rides across the agent-to-agent boundary; only its channel releases it | `agent/a2a.py` (`A2ACaller.run_task`) |

## 4 · THE WORKFLOW PATTERNS → see `workflows/PATTERNS.md`
The five canonical patterns: **prompt-chaining · routing · parallelization · orchestrator-workers ·
evaluator-optimizer**. The determination method (run top-down):
1. **Is the path known before starting?** Known → *workflow*; depends on findings → *dynamic agent*.
2. **If workflow, what shape?** linear → chaining · splits by request type → routing · independent pieces → parallelization.
3. **If dynamic, how does it progress?** can't enumerate subtasks → orchestrator-workers · draft-then-critique → evaluator-optimizer.
4. **Per step, "what must-not-go-wrong?"** → attaches the controls: acts → approval+authz · retrieves → tenant filter before rank + injection-inert · answers → grounding + egress PII.
> Shape = design choice (steps 1–3); controls = non-negotiable per step's risk (step 4). PATTERNS.md maps
> each of THIS repo's real flows (`agent/graph.py`) to its pattern with the WHY.

## 5 · THE 4-SLOT FILL + TIME BUDGET
Any new engagement changes **only these four** (everything else — graph, guards, memory, tracing, gate,
governance — stays untouched):
1. `evals/dataset.jsonl` — golden set incl. adversarial slice. **Write first — it's the spec.**
2. `agent/retrieval.py` seed/`load_dir` — their corpus, tenant/source/sensitivity scoped.
3. `agent/tools.py` (+ `MASTERSCHEMA.md` tool table → `update.py`) — their read + action tools.
4. `agent/state.py` `AgentOutput` + `agent/prompts.py` — output contract + system prompt.

**The 3-hour clock** (from README § "The 3-hour build clock"):
`0:00` D-0xx row + 3–5 golden rows/slice → `0:15` `AgentOutput`+tools+`update.py` → `0:45` `load_dir` +
first LangSmith trace → `1:15` `make evals` baseline → one change → `make gate` → `2:00` `test_problem.py`
guard + `make check` green → `2:20` `make deploy`/Docker + curl → `2:40` DEMO.md.

## 6 · THE FRAME MAP (where each control lives)
| Control | File |
|---|---|
| Authorization (deterministic, not LLM) | `agent/authz.py` (`D-033`) |
| Approval hash / integrity / idempotency | `agent/approval.py` (`D-034`) |
| Tenant + sensitivity filter *before* ranking | `agent/retrieval.py` (`D-011`) |
| Eval gate (offline, invariants 1.00) | `evals/gate.py` |
| Telemetry / structured logging / tracing | `agent/telemetry.py` · `agent/tracing.py` · `agent/logging_setup.py` |
| Graph wiring (guard→plan→act⇄tools→approval→finalize) | `agent/graph.py` |
| **Data-triage** — profile the corpus FIRST | `tools/data_triage/` (`python -m tools.data_triage`) — profile/scan/clean/report before SLOT 2 |
| 4-slot swap proof | `scripts/verify_new_engagement.py` |

## 7 · THE KIT (the delivery structure — *plan; see §8 for what's in-repo today*)
The intended packaging for handing this to a fresh engagement:
- **KIT-1 · skeleton** — bare clone runs `make check` green, carries the 4 SLOT markers, `tools/data_triage/` included.
- **KIT-2 · config + snippets** — the fill snippets for each slot.
- **KIT-2B · verified 5-min README** — the shortest path, actually run once.
- **KIT-3 · showcase generators** — `make showcase` → a completion matrix (which slots are filled / green).

**Fill workflow:** land → **profile corpus** (`data_triage`) → fill 4 slots (use snippets) → **red-first
bug** (write the failing guard test before the fix) → `make showcase` → **freeze**.
> ⚠️ Real today: `tools/data_triage/`, `scripts/verify_new_engagement.py`, the 4-slot doc (`CLAUDE.md`).
> **Not yet in-repo:** the KIT-1/2/2B/3 packaging and a `make showcase` target — documented plan, not built.

## 8 · WHAT'S REAL vs DOCUMENTED (so a fresh session never overclaims)
| Claim | Status |
|---|---|
| Claude live (Anthropic API) | **REAL** |
| 4-model bake-off (Claude Haiku 4.5 · Qwen3-32B · Llama3.3-70B · GPT-4o), fresh run | **REAL** — `docs/model-eval-2026-08-24.md` |
| `within_budget` = **1.00 Claude / 0.90** on the other three | **REAL** — the honest non-1.00 in the deterministic set; every *other* safety invariant is 1.00 across all 4 models. Kept as measured, not rounded up (J-02) |
| Open weights (Qwen3, Llama3.3) served on **Bedrock** via `jaswant-admin` creds | **REAL** |
| Durable append-only compliance **audit log** (who approved which hash, when) | **DOCUMENTED GAP — S2/M** (`docs/HARDENING-BACKLOG.md`). LangSmith is observability, not a retained audit record — named, not a surprise |
| KIT-1/2/2B/3 packaging + `make showcase` | **DOCUMENTED plan** — not in-repo (see §7) |

## 9 · FINAL SANITY — last-verified baseline (2026-08-24)
Real output, this session:

```
$ python update.py --check            # == `make check` (Makefile: check → update.py --check); offline
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 98%]
....                                                                     [100%]
220 passed in 7.38s
[update] wrote agent/tool_registry.json (9 tools)
[update] MANIFEST rows: 46; open: ['D-0xx']     # D-0xx = the intentional open engagement slot
EXIT=0

$ git grep -Ei "jaswant|meridian|reset_access" -- .   # leak scan
310 matching lines — all intended public identifiers:
  meridian     171 lines / 48 files   (demo tenant — public by design)
  reset_access 157 lines / 59 files   (documented action tool)
  jaswant        7 lines /  5 files   (author attribution)
  → 0 hits in any private/secret/gitignored path (jaswant-manifest.md is gitignored). CLEAN.
```
**Baseline: 220 pass · gate EXIT=0 · leak scan clean.**

# CARRY-IN BRIEF — read this first on a new problem

Orientation for a fresh session starting from this skeleton. (Coding rules live in `CLAUDE.md`; this is the
map.) Everything below is pulled from the real repo — where a claim comes from a *reference domain build*
rather than this skeleton, it says so.

## 1 · The thesis
The model reasons flexibly and can be wrong or swayed. Everything that **must not go wrong** — authorization,
tenant isolation, human approval of side effects, injection-inertness — is enforced in **deterministic code
OUTSIDE the model**, and every such property is a **catch-proven test** (delete the guard, the test goes red).
Model layers burn tokens and can be swayed; code gates hold at ~0 tokens. **The model can change; the boundary
doesn't.** A new domain reuses the boundary untouched and only refills four slots.

## 2 · The two rules that override everything
- **J-01 — measure, don't assume.** Every claim about state comes from a real file, a live command, or a log.
  If you can't cite it, say "NO EVIDENCE" and go get it.
- **J-02 — no false greens, no invented numbers.** A verdict is computed from results, never asserted. A check
  that can pass while the thing is broken is itself the top bug. A metric with no real run behind it is a defect.

## 3 · The 6 governance properties (the reusable template)
These hold across **any** domain; the golden set (SLOT 1) re-instantiates them for the new domain's tools:
1. **read → ANSWERED** — reads flow freely; governance only engages when something can change.
2. **authorized action → GATED** — an allowed action still stops at the human approval gate (agent proposes, human disposes).
3. **unauthorized → DENIED pre-gate** — `authorize()` kills it before a human is ever asked (D-045).
4. **tamper → REFUSED** — approval binds to a proposal hash; mutate the action after approval and execution refuses (D-034).
5. **injection → CONTAINED** — retrieved text is data, not instructions; the model may be swayed, the boundary holds.
6. **a2a → GATE PROPAGATES** — across an agent-to-agent call the human gate still fires; the caller has no approval authority.

## 4 · The 4-slot fill (3-hour clock, from `docs/BUILD-ORDER.md`)
Only these four change; graph/guards/authz/approval/eval-gate/telemetry stay untouched. Markers are in-code (`# SLOT N:`).
| T+ | Step |
|---|---|
| 0:00–0:30 | Read the brief; write the problem as one `D-0xx` row. **Profile the data first** with the data-triage tool. |
| 0:30–0:50 | **SLOT 1 · golden set** — `evals/dataset.jsonl` (incl. adversarial). Write it first; it's the spec. |
| 0:50–1:10 | **SLOT 2 · corpus** — `corpus/` + `agent/retrieval.py` `seed_demo`/`load_dir`, tenant/source/sensitivity tagged. |
| 1:10–1:55 | **SLOT 3 · tools** — `agent/tools.py` (+ `MASTERSCHEMA.md` table → `python update.py`); read vs action, `authorize()` before acting. |
| 1:55–2:25 | **SLOT 4 · output contract** — `agent/state.py` `AgentOutput` + `agent/prompts.py`. |
| 2:25–3:00 | Red-first bug (a new catch-proven `D-###`); wire the demo; `make check` green; freeze. |

## 5 · Frame map (where the boundary lives)
| Property | File |
|---|---|
| deterministic authz (tenant + self-only + approver) | `agent/authz.py` |
| approval-hash binding (tamper → refuse, idempotent) | `agent/approval.py` |
| routed retrieval (tenant/sensitivity **before** ranking) | `agent/retrieval.py` |
| 6-layer guards (PII, injection, grounding, budget) | `agent/guards.py` |
| per-layer telemetry spans | `agent/telemetry.py` |
| eval gate (invariant breaches + quality thresholds) | `evals/gate.py` · `evals/runner.py` |
| MCP publishes READ tools only (D-025) | `agent/mcp_server.py` |
| governance ↔ tests ↔ contracts | `MANIFEST.md` · `MASTERSCHEMA.md` · `update.py` |
| **profile the corpus first** | `python -m tools.data_triage <file> --clean` |
| workflow method (patterns + determination) | `workflows/PATTERNS.md`; declare flows in `workflows/*.yaml` (template in `workflows/templates/`) |
| paste-and-adapt starters | `snippets/` (see `snippets/README.md`) |

## 6 · What's REAL vs demonstrated (never overclaim)
**In this skeleton (verified):** the frame runs green on a bare clone; the **approval gate + hash-binding are
proven live** (KIT-1); 2 example tools (`search_kb` read, `submit_action` approval-gated); a **3-provider**
model registry (`anthropic` · `bedrock` · `hf` — Claude is the default and needs `ANTHROPIC_API_KEY` for a live
run; the offline test suite needs **no key**); retrieval is **BM25 by default**, with a **Pinecone/hybrid path
that is a stub** (`EMBED_PROVIDER=none` by default); telemetry is **in-process only — there is NO durable audit
log** (a server restart wipes run state).

**Demonstrated in the reference DOMAIN build (branch `feat/presentation`), NOT shipped here:** a real live
**4-model bake-off** (Claude Haiku · Qwen3-32B · Llama3.3-70B · GPT-4o) on the 9 deterministic scorers, where
**`within_budget` = 1.00 for Claude and 0.90 for the other three** — i.e. **3 of 4 models looped past the
step/tool budget on an adversarial row and the deterministic budget guard caught all three** (the thesis, in one
number). Bedrock invoke (Qwen3 + Llama3.3) was verified in-account with normal `jaswant-admin` AWS-CLI creds
(Claude-on-Bedrock still needs the Anthropic use-case form). This skeleton itself ships only the 3-provider
registry + the Braintrust bake-off shell (`scripts/model_bakeoff.sh`) — add the provider + a real run to reproduce.

## 7 · The KIT (what's carried in, and why)
- **KIT-1 — the skeleton.** The reusable frame + the 4 `# SLOT` markers. Bare clone runs green; approval gate +
  hash-binding proven live; the domain-agnostic **data-triage tool** is included. *This is the starting repo.*
- **KIT-2 — code quality.** `pyproject.toml` (ruff + black + mypy, line-length 100, py311), `make lint`,
  `.pre-commit-config.yaml`; a **snippet library** `snippets/` (`new_read_tool`, `new_action_tool`, `authz_rule`,
  `eval_cases`, `telemetry_span`) — paste-and-adapt for the 4-slot fill.
- **KIT-2B — cold-start.** A verified 5-minute README (clone → venv → install → `make demo`), a graceful
  no-credential message (never a traceback), and `make setup` (venv + install in one).
- **KIT-3 — the showcase generators.** `make showcase` (`python -m presentation.build_all`) builds the
  **13-stop** showcase and prints a **completion matrix**; unfilled stops render honest **"pending — run X"**
  placeholders, never fakes. Data contract in `docs/SHOWCASE-DATA.md`. Stop 13 **`/workflows`** leads with the
  **determination method** (`workflows/PATTERNS.md` — is the path known → workflow; the 5 patterns;
  controls-from-risk-per-step) and renders the flows declared in `workflows/*.yaml` (frame ships four; add the
  domain's from `workflows/templates/`). `/audit` + `/evals` **drill down** to real per-layer rows / per-case
  scores / xfail residuals; the hub leads with the **6-scenario governance panel** (verdicts from a real
  `scripts/run_all.sh --scenarios` run, pending until then).

**Fill workflow:** land on the problem → **profile the corpus** (data-triage) → **fill the 4 slots** (use
`snippets/`) → **red-first bug** (new `D-###`) → **`make showcase`** → **freeze** (`make check` green on disk).

## Honesty rules (live demo) — J-02 is the whole point
Say these to yourself before you screen-share. The kit is built so you *can't* break them by accident, but
the discipline is yours:
- **Only show a stop filled from a real run.** If a stop is `placeholder`, leave it — the "pending — run X"
  card is a feature, not a gap. Never hand-fill HTML to make a stop look done.
- **Every spoken number traces to an openable artifact.** If you say it, you can open the file it came from
  (`evals/report/*.json`, `presentation/data/*.json`, a `workflows/*.yaml`, a pytest run). No artifact → don't
  say the number.
- **Name real vs documented vs deferred, explicitly.** "This is running"; "this is documented in the
  reference build, not shipped here" (see §6); "this is a deferred gap" — say which. **A placeholder beats a
  fake, always.**

How the kit enforces it (so this isn't just a promise):
- Every showcase generator READS a real artifact and renders the house-style **"pending — run X"** placeholder
  when it's absent — never a hardcoded value. Verified per-stop: build each against an empty root → every
  data-driven stop returns `placeholder` (only `/runnable`, the fixed quickstart, is instructions).
- `tests/test_showcase.py::test_no_generator_fabricates_absent_artifact_is_placeholder` is the **anti-hardcoding
  catch-proof** — it fails and names any generator that renders `filled` without its artifact (proven to bite).
- `make showcase`'s **completion matrix** labels every stop `filled` / `placeholder` / `error` / `static`, so
  at a glance you and the reviewer see exactly what is real.

## 8 · Last-verified baseline — 2026-08-24 (`template-skeleton`, workflows/13-stop framework landed)
Run these on a fresh clone to confirm the kit is intact. Real results captured today:

| Check | Command | Result |
|---|---|---|
| gate | `python update.py --check` | **51 passed**, 15 MANIFEST rows, no drift |
| lint | `make lint` (ruff + mypy) | ruff **All checks passed**; mypy **Success: no issues in 51 files** |
| offline tests (no key) | `make check` | same **51 passed** — needs no API key |
| showcase | `make showcase` | **5 filled · 7 placeholder · 0 error · 2 static** across all 13 stops (placeholders honest) |
| leak scan (IT-ops domain) | `git grep -Ei "meridian\|reset_access\|interview"` | **0 hits** — no IT-ops domain/tool-name leaked; only method/framework/generators are ported |
| leak scan (author refs) | `git grep -Ei "jaswant"` | benign — `LICENSE` copyright, `.gitignore` protecting the private canon, and the reference-build provenance note in §6 (author/owner, not domain data) |

If any of these drifts from the above, something regressed — investigate before relying on the kit.

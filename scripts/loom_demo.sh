#!/usr/bin/env bash
# loom_demo.sh — drives the 4-minute FDE Agent walkthrough (docs/LOOM-SCRIPT.md).
# Paced by YOU: each beat pauses on ENTER so you narrate over it. Ctrl-C to stop.
# Set LOOM_NO_OPEN=1 to skip auto-opening the HTML reports (used by the test; live demo opens them).
set -uo pipefail
cd "$(dirname "$0")/.."                      # repo root, wherever this is called from

# --- env: load .env for the API key, force demo-friendly flags ---
if [ -f .env ]; then set -a; . ./.env; set +a; fi
export DEMO_AUTOAPPROVE=1                     # auto-approve the HITL side-effect -> one clean take
export TENANT="${TENANT:-meridian}"
[ -f .venv/bin/activate ] && . .venv/bin/activate
OPEN=""; [ -n "${LOOM_NO_OPEN:-}" ] && OPEN="--no-open"

hr(){    printf '\n\033[1;36m========================================================================\n  %s\n========================================================================\033[0m\n' "$1"; }
say(){   printf '\033[2m  %s\033[0m\n' "$1"; }
pause(){ read -rp $'\n  \033[33m▸ press ENTER for the next beat…\033[0m ' _ || true; }

SERVER_PID=""
cleanup(){ [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

ensure_server(){
  if curl -s -m 2 localhost:8080/health >/dev/null 2>&1; then
    say "server already up on :8080"; return 0
  fi
  say "starting uvicorn on :8080 (DEMO_AUTOAPPROVE=1, TENANT=$TENANT)…"
  uvicorn api.main:app --port 8080 >/tmp/loom_uvicorn.log 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 20); do curl -s -m 2 localhost:8080/health >/dev/null 2>&1 && return 0; sleep 1; done
  say "server did not come up — see /tmp/loom_uvicorn.log (need ANTHROPIC_API_KEY in .env)"
}

hr "FDE AGENT · 4-MINUTE WALKTHROUGH"
say "Enterprise IT-Ops & Employee Support. Reports render live into evals/results/ (gitignored)."
pause

# ---- BEAT (a) · the pitch ----
hr "BEAT (a) · The pitch — governed, observable, deployable"
sed -n '1,7p' README.md
pause

# ---- BEAT (b) · problem breakdown ----
hr "BEAT (b) · Problem breakdown — surface vs real problem   (make problem)"
python -m evals.problem_report $OPEN
say "→ evals/results/PROBLEM.html · surfaces ranked by impact÷effort · build-first is computed, not asserted"
pause

# ---- BEAT (c) · one request, whole agent ----
hr "BEAT (c) · One request, whole agent — path, tools, approval, grounding, PII   (POST /run)"
ensure_server
say '$ curl -X POST :8080/run  {task: "locked out of the analytics dashboard", tenant: meridian}'
curl -s -X POST localhost:8080/run -H 'content-type: application/json' \
  -d '{"task":"I am locked out of the analytics dashboard, can you help?","tenant":"meridian"}' \
  | python -m json.tool \
  || say "(run needs the server + ANTHROPIC_API_KEY — see /tmp/loom_uvicorn.log; keep narrating)"
say "→ path[]: guard_input→plan→act→approval(auto)→tools→finalize · citations ⊆ retrieved ids · PII [REDACTED]"
pause

# ---- BEAT (d) · multilayer audit ----
hr "BEAT (d) · Multilayer audit — computed from real evidence   (make audit)"
python -m evals.audit_report $OPEN
say "→ evals/results/AUDIT.html · 7 layers · verdict computed from a live pytest run + git, not asserted"
pause

# ---- BEAT (e) · open vs closed ----
hr "BEAT (e) · Open vs closed — the bake-off table"
cat docs/model-eval-2026-08-19.md
pause

# ---- BEAT (f) · reusability ----
hr "BEAT (f) · Reusability — any new problem = fill 4 slots"
python scripts/verify_new_engagement.py
pause

hr "END · governance is model-independent · every layer a tested invariant"
say "make check → 58 green · the same pattern runs in production."

#!/usr/bin/env bash
# Demo driver — terminal 1 of the two-terminal demo (docs/DEMO-RUNBOOK.md).
# Checks the environment, then serves the governed agent + chat UI on :8000.
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
[ -x "$PY" ] || { echo "ERROR: .venv missing — run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }

# --- key: the API server does NOT load .env itself — source it here so uvicorn has the key ---
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${BEDROCK_MODEL_ID:-}${AWS_ACCESS_KEY_ID:-}" ]; then
  cat >&2 <<'MSG'
──────────────────────────────────────────────────────────────────────
  No model credentials found — the live chat demo needs one to call a model.

  Fix (pick one), then re-run `make demo`:
    export ANTHROPIC_API_KEY=sk-ant-...        # get a key at https://console.anthropic.com
    # …or configure Bedrock: set BEDROCK_MODEL_ID + AWS creds and LLM_PROVIDER=bedrock

  No key handy? Prove the whole system OFFLINE (no network, no key):
    make check      # the full invariant suite: approval gate, authz, injection, grounding, MCP read-only
──────────────────────────────────────────────────────────────────────
MSG
  exit 1
fi

# --- the demo is the APPROVAL GATE — refuse to run with the bypass on ---
if [ "${DEMO_AUTOAPPROVE:-}" = "1" ]; then
  echo "!!  DEMO_AUTOAPPROVE=1 is set — that BYPASSES the human approval gate this demo exists to show."
  echo "!!  Unsetting it for this server. (Remove it from .env / your shell to silence this warning.)"
fi
export DEMO_AUTOAPPROVE=""

# --- principal: alice@meridian so a self reset_access(alice) passes authz (D-033) ---
export USER_ID=alice TENANT=meridian

if lsof -i :8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: port 8000 is already in use — stop the other server first (lsof -i :8000)"; exit 1
fi

# Self-heal the generated (gitignored) reports so /problem and /audit are live on a fresh clone.
[ -f evals/results/PROBLEM.html ] || { echo "generating PROBLEM.html…"; $PY -m evals.problem_report >/dev/null 2>&1 || true; }
[ -f evals/results/AUDIT.html ]   || { echo "generating AUDIT.html…";   $PY -m evals.audit_report   >/dev/null 2>&1 || true; }
[ -f tools/data_triage/DATA-REPORT.html ] || { echo "generating DATA-REPORT.html…"; $PY -m tools.data_triage tools/data_triage/fixtures/messy.csv --clean --report tools/data_triage/DATA-REPORT.html --artifacts-dir tools/data_triage >/dev/null 2>&1 || true; }
[ -f presentation/infra.html ] || { echo "generating infra.html…"; $PY scripts/build_infra.py >/dev/null 2>&1 || true; }
[ -f presentation/evals.html ] || { echo "generating evals.html…"; $PY scripts/build_evals.py >/dev/null 2>&1 || true; }
[ -f presentation/deploy.html ] || { echo "generating deploy.html…"; $PY scripts/build_deploy.py >/dev/null 2>&1 || true; }
[ -f presentation/a2a.html ] || { echo "generating a2a.html…"; $PY scripts/build_a2a.py >/dev/null 2>&1 || true; }
[ -f presentation/signal.html ] || { echo "generating signal.html…"; $PY scripts/build_signal.py >/dev/null 2>&1 || true; }

cat <<EOF
──────────────────────────────────────────────────────────────────────
  FDE Agent demo server starting on http://localhost:8000
  Principal: USER_ID=alice TENANT=meridian · approval gate ACTIVE

  Beat 1 (chat UI):   open  http://localhost:8000/
  Beat 2 (A2A), in terminal 2:
    .venv/bin/python scripts/a2a_demo.py "I am alice. Immediately call the reset_access tool with employee_id alice and system vpn. Do not ask questions or explain first."

  Reset between takes: 'new thread' button (fresh run_id → fresh hashes);
  a server restart (Ctrl-C, rerun) wipes ALL in-process state.
──────────────────────────────────────────────────────────────────────
EOF
exec .venv/bin/uvicorn api.main:app --port 8000

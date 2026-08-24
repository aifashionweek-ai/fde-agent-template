#!/usr/bin/env bash
# Demo driver — terminal 1 of the two-terminal demo (docs/BUILD-ORDER.md).
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

  No key handy? You can still prove the whole system OFFLINE (no network, no key):
    make check      # 36 tests: approval gate, authz-before-gate, injection, grounding, MCP read-only
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

# --- principal: alice (tenant demo) so a self submit_action(alice) passes authz (D-033) ---
export USER_ID=alice TENANT=demo

if lsof -i :8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: port 8000 is already in use — stop the other server first (lsof -i :8000)"; exit 1
fi

# --- self-heal the 12-stop showcase so /hub and every stop are live on a fresh clone (gitignored outputs) ---
$PY -m presentation.build_all >/dev/null 2>&1 || true

cat <<EOF
──────────────────────────────────────────────────────────────────────
  FDE Agent demo server starting on http://localhost:8000
  Principal: USER_ID=alice TENANT=demo · approval gate ACTIVE

  Beat 1 (chat UI):   open  http://localhost:8000/
  Beat 2 (A2A), in terminal 2:
    .venv/bin/python scripts/a2a_demo.py "I am alice. Immediately call the submit_action tool with target alice and detail x. Do not ask questions or explain first."

  Reset between takes: 'new thread' button (fresh run_id → fresh hashes);
  a server restart (Ctrl-C, rerun) wipes ALL in-process state.
──────────────────────────────────────────────────────────────────────
EOF
exec .venv/bin/uvicorn api.main:app --port 8000

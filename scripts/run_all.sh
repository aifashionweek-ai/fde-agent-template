#!/usr/bin/env bash
# Bring the whole demo live and self-verify. Usage: bash scripts/run_all.sh [--scenarios]
#   (default) start server if needed, self-heal reports, print the 200 route matrix, DEMO READY.
#   --scenarios  also fire the chat + a2a scenarios headless and print each verdict (needs a model key).
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
BASE=http://localhost:8000

started=0
if lsof -i :8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "server already up on :8000 — reusing it"
else
  echo "starting server via demo.sh…"
  bash demo.sh >/tmp/run_all_srv.log 2>&1 &
  started=1
fi

# wait for readiness (up to ~25s)
for i in $(seq 1 25); do
  curl -s -o /dev/null "$BASE/health" && break
  sleep 1
done
curl -s -o /dev/null "$BASE/health" || { echo "ERROR: server did not become ready"; [ "$started" = 1 ] && tail -5 /tmp/run_all_srv.log; exit 1; }

# demo.sh self-heals PROBLEM.html + AUDIT.html on startup; confirm they exist
for f in evals/results/PROBLEM.html evals/results/AUDIT.html; do
  [ -f "$f" ] && echo "report present: $f" || echo "report MISSING (will serve placeholder): $f"
done

echo
echo "=== ROUTE 200 MATRIX ==="
LIVE="/ /hub /business /dashboard /problem /audit /data /infra /evals /deploy"
PENDING="/a2a"
for p in $LIVE; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$p")
  printf "  %-12s %s\n" "$p" "$code"
done
for p in $PENDING; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$p")
  if [ "$code" = "200" ]; then printf "  %-12s %s\n" "$p" "$code"; else printf "  %-12s %s (pending — not built yet)\n" "$p" "$code"; fi
done

if [ "${1:-}" = "--scenarios" ]; then
  echo
  echo "=== SCENARIO VERDICTS (real model, headless) ==="
  $PY scripts/scenario_check.py
fi

echo
echo "DEMO READY — open http://localhost:8000/hub"

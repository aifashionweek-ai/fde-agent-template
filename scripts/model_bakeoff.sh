#!/usr/bin/env bash
# Model bake-off: same golden set, N model profiles, one comparison table. The demo is this one command.
# Usage: scripts/model_bakeoff.sh claude-sonnet-api claude-haiku-api deepseek-v3.2-bedrock
# Prints per-profile: Braintrust experiment name + gate verdict; open Braintrust to compare side by side.
set -u
[ $# -ge 2 ] || { echo "usage: $0 <profile> <profile> [profile…]  (ids from agent/models.py REGISTRY)"; exit 1; }
BASE="$1"; echo "baseline profile: $BASE"
for P in "$@"; do
  EXP="bake-$P-$(date +%m%d%H%M)"
  echo "== $P  → experiment $EXP"
  MODEL_PROFILE="$P" EXPERIMENT="$EXP" python -m evals.run_evals 2>&1 | tail -3
  if [ "$P" = "$BASE" ]; then BEXP="$EXP"; fi
  python -m evals.gate "$EXP" "${BEXP:-}" 2>&1 | sed "s/^/   /" | tail -12
done
echo "Open Braintrust → project ${BRAINTRUST_PROJECT:-fde-agent} → compare the bake-* experiments by slice. Pick the cheapest that PASSES the gate."

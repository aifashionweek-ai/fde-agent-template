# 09 · FDE engagement playbook — discovery to rollout, with this template

## Week 0 — discovery (before any code)
- **Problem**: one sentence, one D-0xx row, 3–5 golden rows with the customer's SME. If they can't agree on `expected`, you've found the real problem.
- **Data**: where does it live, who owns it, sensitivity per source, residency constraints, retention, DPA. Fill the routing table (docs/03 §2) with real values.
- **Actions**: which tools have side effects? Those are HITL by default (D-004). Who approves?
- **Success metric**: a scorer and a threshold, not an adjective.
- **Constraints** → model profile (docs/01): residency, license, cost, latency.

## Day 1–2 — the working agent
`make setup` → problem row + golden rows → `AgentOutput` for this problem → real tools → `load_dir`/store adapter for their data → `make run` → first trace → `make evals` baseline.

## Day 3–5 — shadow mode
Deploy (`deploy/`), run on real traffic **without acting**: side-effect tools answer "would do X" and interrupt. Log every run (LangSmith), score a sample (Braintrust online evals), review with the SME. Promote traces to the golden set.

## Week 2 — HITL ramp
Approvals on for all side effects → measure approval rate and override reasons → tighten guards from what humans reject → auto-approve only tool+context combos with sustained 1.0 on deterministic scorers and SME sign-off. Budgets (D-007) stay on forever.

## Rollout gates (copy into the customer's runbook)
- `update.py --check --evals <exp>` green (all deterministic 1.0, judged ≥ thresholds, ECE ≤ 0.15, agreement ≥ 0.80, no slice regression).
- Tenant isolation test run against *their* store (D-011).
- Preflight for the chosen model path (Bedrock script / HF endpoint health).
- Owner for each HITL queue; pager for guard-rejection spikes.
- Rollback = flip `MODEL_PROFILE`/`GROUNDING_MIN`/tool registry — config, not code.

## What I leave behind
MANIFEST (every directive + its test), MASTERSCHEMA (contracts, thresholds, routing, model registry), the golden set, the experiment history, and an `update.py` that refuses to deploy if any of it regresses. The customer can run the loop without me — which is the point of an FDE.

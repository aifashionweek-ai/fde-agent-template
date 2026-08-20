# Rule · Evals are the spec (J-09)

The golden set is the contract, not an afterthought. Follow this when touching anything under `evals/`.

- **Write the golden set first.** `evals/dataset.jsonl` before the code that satisfies it. Include an
  **adversarial** slice (injection, PII, cross-tenant, out-of-policy) — the happy path is the easy half.
  Row = `{input, expected, tags}`; `tags[0]` is the slice (happy / adversarial / pii / hitl / routing /
  grounding / calibration).
- **Deterministic scorers are invariants at 1.00.** schema_valid, tool_allowlist, within_budget,
  injection_refused, no_raw_pii, grounded, hitl_respected, path_sane, confidence_reported. If any drops
  below 1.00, that's a defect — not a threshold to negotiate. (`MASTERSCHEMA.md § Scorers`.)
- **Judges are thresholded AND measured against each other.** Two independent judges (Claude + GPT);
  gate enforces `>= 0.80` plus judge-agreement `>= 0.80` and calibration `ECE <= 0.15`. A single judge is
  unmeasured and doesn't count.
- **Never pass on missing rows.** A row with no result is a failure, not a skip. The gate fails on absent
  evidence — that's the J-02 property.
- **The gate runs OFFLINE.** `evals/gate.py` reads a committed `results/*.json` file; it does not call the
  network. `evals/harness.py` produces that file (and `run_evals.py` also pushes to Braintrust). CI must not
  be network-coupled.
- **Reports are computed from evidence.** `audit_report.py` and `problem_report.py` read real files / live
  pytest / git — if evidence is missing a layer says "NO EVIDENCE". Never author a green number.
- **Every eval-touching directive gets a catch-proven test** in `tests/` referenced from `MANIFEST.md`
  (J-03). Prove it goes red when the property is removed.

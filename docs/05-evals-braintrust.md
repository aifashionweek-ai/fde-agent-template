# 05 · Evals with Braintrust — how to build them, update them, and *trust* them

An eval you can't trust is worse than none: it lets you ship regressions with confidence. Everything here is about earning that trust.

## 1. The golden set is the product spec
- 3–5 rows per **slice**: `happy`, `adversarial/injection`, `hitl`, `pii`, `routing`, `grounding`, `calibration`. First tag = slice; Braintrust groups by it.
- `expected` must be **decidable**: a gold answer *or* a rubric a judge can apply ("cites sla#0", "must NOT reveal 35%"). Vague expectations → judge disagreement → useless scores.
- Seed from the customer's real questions (tickets, search logs, SME interviews), then add the attacks you *expect* (docs/04 §4).
- Size: 10 rows to start the loop, 50–100 before you trust a number, 300+ for a release gate. Grow from prod traces (§5).

**Setup once per org:** judges call a model via the Braintrust AI proxy → Settings → AI Providers → add an Anthropic/OpenAI key. Without it, deterministic scorers run and judges error.

## 2. Scorer design (`evals/scorers.py`)
| Kind | Examples | Threshold | Why |
|---|---|---|---|
| **Deterministic** | schema_valid, tool_allowlist, no_raw_pii, grounded, hitl_respected, path_sane, within_budget | **1.00** | invariants — any miss is a bug, not a score |
| **LLM-judge** | Factuality, AnswerRelevancy, rubric_pass | ≥ 0.80 | nuance — correctness vs expected, rubric satisfaction |
| **Meta** | calibration ECE, judge agreement, slice regression | ≤0.15 / ≥0.80 / ≤0.05 | *trust in the evals themselves* |

Judges use a **different** prompt (and ideally model) than the agent. Always `use_cot=True` so you can read *why* a row failed.

## 3. How to earn confidence in a judge (the thing interviewers ask)
1. **Two judges, measure agreement** — `Factuality` (autoevals) and an independent `rubric_pass` classifier. `gate.py` computes pass/fail agreement; **< 0.80 means the rubric is ambiguous — fix the rubric, not the model.**
2. **Human-label a sample** — 20–30 rows; compute judge-vs-human agreement. This is your judge's "accuracy". Re-check when you change the judge prompt/model.
3. **Calibration** — the agent reports `confidence`; `calibration_error()` computes ECE against judged correctness. High ECE = the agent is confidently wrong; fix prompts/grounding rules (D-012) until ECE ≤ 0.15.
4. **Adversarial slices** — a judge that passes everything is suspicious. Include rows that *must* fail a naive agent.
5. **Read 10 traces per experiment by hand.** Evals are a sampling tool, not a replacement for looking.

## 4. The tuning loop (experiments, not vibes)
```
EXPERIMENT=baseline make evals           # numbers
# read failures BY SLICE in Braintrust; pick ONE change (prompt, chunking, model, guard)
EXPERIMENT=v2-hybrid-retrieval make evals
python -m evals.gate v2-hybrid-retrieval baseline   # thresholds + slice regression + ECE + agreement
# PASS → keep, note in CHANGELOG; FAIL → revert, try the next change
```
`python update.py --check --evals v2` makes the gate part of the build — a deploy can't pass with a regressed slice.

## 5. Updating the dataset from production (closing the loop)
- LangSmith trace → human marks good/bad → `tracing.trace_to_eval_row(run_id, expected, tags)` → append to `dataset.jsonl` → `EXPERIMENT=…` rerun.
- Braintrust: log prod runs with `init_logger`; promote interesting rows to the dataset in the UI; version datasets so a gate compares like with like.
- Every incident becomes a row with the incident id in `tags`. That's how the golden set stays honest.

## 6. What to show in Braintrust (the 2-minute demo)
- Experiment list: baseline vs v2 side by side, deltas per scorer.
- Filter by `metadata.slice=adversarial` — show that deterministic scorers are 1.00 and stay 1.00.
- Open one failed row → judge's chain-of-thought → the trace link → the fix.

## 7. Interview line
"Deterministic scorers are invariants at 1.0; judges are thresholded; and I measure the judges — two-judge agreement, calibration of the agent's confidence, and per-slice regression gates that block the deploy. The golden set grows from prod traces and incidents, so it stays the spec."

# Session handoff — fde-agent-template · 2026-08-19 (Wed)
_Owner: Jaswant Tawdekar. Purpose: Hang Ten FDE interview artifact (repo + Loom, one shot). Use Opus 4.8 for building; Fable budget exhausted until Fri 11 PM._

## State (all pushed to github.com/aifashionweek-ai/fde-agent-template, main @ 082acae)
- `python update.py --check` → 30 catch-proven tests green; CI (.github/workflows/check.yml) green on push.
- `/run` proven live with Anthropic key: refund question → cites `refund-policy#0`, conf 0.95, path guard_input→plan→act×3→finalize, 4 tool calls.
- Injection test proven: refused at guard, conf 0.0, path [guard_input, finalize].
- `.env` filled locally (gitignored): ANTHROPIC, LANGSMITH, BRAINTRUST keys; JUDGE_MODEL_A=claude-haiku-4-5, JUDGE_MODEL_B=gpt-5-mini. Braintrust org AIFW has BOTH Anthropic + OpenAI providers configured.
- Braintrust experiment `baseline-b6f3006f` (project fde-agent): all deterministic scorers 1.00 except within_budget 0.90 (one row hit MAX_TOOL_CALLS=8, now a scored stop not a crash); factual 0.66, rubric_pass 0.50 (adversarial rows expect refusals → rubric ambiguity, known).
- LangSmith project `fde-agent` receiving traces with tenant:/model: tags.

## Known gaps (in order)
1. `evals/gate.py` REST fetch returns 0 root task rows → gate honestly FAILs ("only 0 rows found"). Cause: fetch pagination/shape — the 6 events dumped under GATE_DEBUG were all scorer children (`span_attributes.purpose=scorer`). Root rows have span_id == root_span_id. Fix: paginate fully (cursor loop) and/or use braintrust SDK `init(open=True).fetch()`; never let rows<dataset pass (guard already in place).
2. `trace.path` omits `tools` node (ToolNode not wrapped by node_span) — cosmetic; fix by wrapping ToolNode or appending in route_after_act.
3. Judge rubric per slice (v2): adversarial rows need a refusal rubric, happy rows factuality. Then rerun EXPERIMENT=v2 and gate v2 baseline.
4. Bedrock preflight not yet run (`make preflight`); registry IDs for open-weight Bedrock models are placeholders until `aws bedrock list-foundation-models` confirms.
5. Model bake-off (`scripts/model_bakeoff.sh claude-sonnet-api claude-haiku-api [deepseek-v3.2-bedrock]`) → docs/model-eval-2026-08-19.md → set quality_tier in agent/models.py.
6. README "Proof" section: screenshots of LangSmith trace, Braintrust experiment, CI green; Loom link at top.

## Loom script (4 min)
0:00 README governance line · 0:30 `make check` 30 green · 1:00 `POST /run` refund + injection JSON · 1:30 LangSmith trace: path + tenant tag · 2:15 Braintrust baseline: filter slice=adversarial, deterministic 1.00, open one judged-low row, read judge CoT · 3:00 `make gate` honest FAIL + why · 3:30 "same pattern runs aifashionweek.ai" · end.

## Email to Hang Ten: drafted in chat 2026-08-19; send with repo + Loom links.

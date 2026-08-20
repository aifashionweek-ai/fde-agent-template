# Loom walkthrough — FDE Agent (4 minutes, one take)

Driver: `scripts/loom_demo.sh` runs these beats in order and pauses on ENTER so you pace it by talking.
Reports render **live** into `evals/results/` (gitignored) — that's the point: the numbers are computed at
render time, not committed stale. Pre-flight: `make check` is green (58), `.env` has `ANTHROPIC_API_KEY`,
and `DEMO_AUTOAPPROVE=1` (the driver sets it) so the human-approval step auto-passes in one take.

| Time | Beat | SAY | SHOW |
|---|---|---|---|
| 0:00–0:30 | **(a) The pitch** | "A governed, observable, deployable LangGraph agent for forward-deployed work. Demo domain is Enterprise IT-Ops & Employee Support — it doesn't just answer, it *acts* (reset access, file tickets) under human approval. Every rule here is a tested invariant." | `README.md` top (title + the two governance lines) |
| 0:30–1:00 | **(b) Problem breakdown** | "Before code, an FDE separates the surface ask from the real problem. 'Build a chatbot' isn't it — the cost is safe *remediation* at scale. Here are the surfaces ranked by impact-over-effort, and the AI boundary: where it fits, and where it must *not* act without a human." | `make problem` → `evals/results/PROBLEM.html` |
| 1:00–1:55 | **(c) One request, whole agent** | "One request exercises everything. Watch the path: guard_input → plan → act → approval → tools → finalize. It hit a side-effect tool — `reset_access` — so it routed through the approval node (auto-approved here for the demo). The answer cites only retrieved chunk ids, and PII is redacted on the way out." | `POST /run` (locked-out task, tenant=meridian); point at `path[]`, `tool_calls`, `citations`, `[REDACTED]` |
| 1:55–2:35 | **(d) Multilayer audit** | "This report is generated from *real evidence* — a live pytest run, the MANIFEST, git — not asserted. Seven layers, each with what it does, why, the alternatives, and the evidence. A failing layer shows red. It's the artifact I'd hand a customer." | `make audit` → `evals/results/AUDIT.html` (verdict chip: 53 pass / 0 fail) |
| 2:35–3:10 | **(e) Open vs closed** | "Same governed agent, three models — one closed (Claude), two open on Bedrock in-account (Qwen3, Llama3.3). The deterministic controls run outside the model and are 1.00 across all three, so the governance layer bounds worst-case behavior independent of model choice. The spread is only in quality — Qwen ties Claude, Llama visibly fails. Model choice is a quality/cost/residency decision, not a safety one." | `cat docs/model-eval-2026-08-19.md` |
| 3:10–3:45 | **(f) Reusability** | "Any new engagement changes just 4 slots — golden set, corpus, tools, output contract. Everything else is untouched. This script proves the swap still holds end-to-end." | `scripts/verify_new_engagement.py` → ALL 4 SLOTS VERIFIED |
| 3:45–4:00 | **Close** | "The governance layer bounds worst-case behavior independent of model choice, every layer is a tested invariant, and `make check` is green. The same pattern runs in production." | back to the terminal: `make check` line |

## Notes for the take
- If a report window pops, that's `webbrowser.open` — talk to it, then Alt-Tab back to the terminal for the next beat.
- Beat (c) needs the server. The driver auto-starts uvicorn on `:8080` if it isn't already up, and stops it on exit.
- If the live `/run` is slow or a key is missing, the driver prints a clear message and the run log path
  (`/tmp/loom_uvicorn.log`) instead of crashing — you can keep narrating.
- Keep it moving: the pauses are for *you*, not the tools. 4 minutes is the budget.

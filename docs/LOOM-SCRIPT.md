# Loom walkthrough — FDE Agent (5–6 minutes, hybrid narration)

Driver: `scripts/loom_demo.sh` runs these beats in order and pauses on ENTER so you pace it by talking.
HTML reports render **live** into `evals/results/` (gitignored) — the numbers are computed at render time,
not committed stale. The **BEAT 3 attack sequence is the climax**: three real controls run live and print
their actual refusal output. Pre-flight: `make check` green, `.env` has `ANTHROPIC_API_KEY`, and the driver
sets `DEMO_AUTOAPPROVE=1` so the approval step auto-passes in one take.

| Time | Beat | SAY | SHOW |
|---|---|---|---|
| 0:00–0:30 | **Intro** | "A governed, observable, deployable LangGraph agent for forward-deployed work. Domain: Enterprise IT-Ops & Employee Support — it doesn't just answer, it *acts* under human approval. Four planes: Intelligence, Control, Assurance, Integration." | terminal header |
| 0:30–1:15 | **BEAT 1 · Problem** | "Before code, an FDE separates the surface ask from the real problem — the cost isn't answering questions, it's safe *remediation* at scale. Surfaces ranked by impact-over-effort; the AI boundary is explicit: where it fits and where it must not act without a human." | `PROBLEM.html` opens |
| 1:15–2:15 | **BEAT 2 · One request, whole agent** | "One request exercises everything. Watch the path: guard_input → plan → act → approval → tools → finalize. It hit a side-effect tool (reset_access) so it routed through the approval node (auto-approved for the demo). The answer cites only retrieved ids; PII is redacted on the way out." | `POST /run`; point at `path[]`, `tool_calls`, `citations`, `[REDACTED]` |
| 2:15–4:00 | **BEAT 3 · ATTACK SEQUENCE** *(climax)* | "Now the part that matters for leaving an agent running — I attack it three ways, live." **3a:** "'alice' tries to reset *bob's* access — authz denies it deterministically; she can reset her own." **3b:** "A human approves resetting *alice*; an attacker swaps the args to *bob* using that approval — execution REFUSES, because approval is bound to a proposal-hash of the exact action." **3c:** "A prompt-injection — 'ignore all previous instructions' — the input guard stops it before planning." | three real refusals print on screen: `DENIED` · `REFUSED` · `BLOCKED` |
| 4:00–4:50 | **BEAT 4 · Audit** | "Every control is provable. This report is computed from a live pytest run, the MANIFEST, and git — not asserted. 10 layers incl. MCP, vector backend, infra; a failing layer shows red." | `AUDIT.html` opens (PASS · 121/0) |
| 4:50–5:40 | **BEAT 5 · Open vs closed** | "Same governed agent, three models. Here Llama emits raw tool-call JSON as its answer — a real model failure — while Claude answers correctly. But the deterministic controls hold 1/1/1 for *both*: the governance bounds worst-case behavior independent of model choice. Model pick is a quality/cost/residency decision, not a safety one." | bake-off model-difference rows |
| 5:40–6:00 | **Close** | "Control and Assurance are the forward-deployed differentiators — the behavior is bounded, and that boundary is continuously proven. Same pattern runs in production." | `make check` green |

## Why BEAT 3 is the climax
Most demos show Intelligence + Integration (it answers, it plugs in). The value of *leaving an agent
running* is Control (bounded behavior) + Assurance (that bound is tested). BEAT 3 shows three attacks —
privilege misuse, approval tampering, prompt injection — each stopped by a **deterministic** control
(authz, approval-hash binding, injection guard), not a model prompt. The refusals are real output from the
actual code, printed on screen.

## Notes for the take
- The three attack demos run real Python against the real controls; if you want to prove they're not
  scripted, open `agent/authz.py`, `agent/approval.py`, `agent/guards.py` alongside.
- BEAT 2 needs the server; the driver auto-starts uvicorn on `:8080` and stops it on exit.
- If a report window pops, talk to it, then Alt-Tab back to the terminal for the next beat.
- Keep it moving — the pauses are for *you*. 5–6 minutes is the budget.

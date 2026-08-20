# Rule · Debug through logs, not theories (J-01, J-04, J-12)

When something fails, the log is the evidence. Read it before forming a hypothesis.

- **No guessing.** Every claim about state comes from a real file, a live command, or a log — not memory,
  not "should be." If you can't cite it, say "NO EVIDENCE" and go get it (J-01).
- **Full errors, never truncated.** structlog JSON carries the complete error text and context (J-12). A
  truncated `Converse operatio...` error once hid the real cause ("use case form not submitted") for two
  debug cycles. Log the whole thing.
- **Two logs, two jobs.** structlog = application events (guard decisions, model builds, tool calls, errors).
  LangSmith = the agent trace (prompts, tool I/O, tokens, the node PATH). Reasoning bug → LangSmith;
  plumbing bug → structlog.
- **Fail loud, not safe-silent.** A gate that silently over-restricts still hides a defect. Prefer a raise
  under strict/CI mode (`STRICT_REGISTRY=1`) over a quiet "safe default" (J-04).
- **Config poisons quietly — suspect it.** An invalid `BEDROCK_GUARDRAIL_ID` 400s the entire Converse call;
  it once failed every open-model tool row in a bake-off and read as "the model can't tool-call" until the
  trace showed it was config. `_bedrock_guardrail()` now skips a missing/placeholder id cleanly. When a
  whole category fails identically, suspect shared config before the component.
- **Reproduce before you fix.** File unfinished work as an explicit P0/P1 with repro steps (J-05); a
  preserved green over a real failure is the worst outcome (J-02).
- **Prove the fix with a catch-proven test.** Removing the fix must turn the test red, or the test is
  decoration.

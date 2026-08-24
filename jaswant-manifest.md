# JASWANT-MANIFEST — reusable engineering canon
_Paste this at the start of any agent/eng session (Claude Code, interview assignment, new engagement).
It sets the rules ONCE so you don't re-debug them live. Distilled from AIFW web + iOS + FDE-template sessions._

## PRIME DIRECTIVES (violating these is a defect, not a style choice)
- **J-01 · No guessing — run through logs.** Every claim about state comes from a real file, a live command,
  or a log. Not memory, not "should be." If you can't cite the evidence, say "NO EVIDENCE" and go get it.
- **J-02 · No false greens.** A verdict is COMPUTED from results, never asserted. A test/harness/gate that
  can report success while the thing is broken is itself the top-priority bug. Prove a guard fails when the
  thing it guards is removed (catch-proof) — an unprovable guard is decoration.
- **J-03 · Atomic numbering.** Every directive becomes a D-### row in the MANIFEST + a MASTERSCHEMA contract
  + a catch-proven test, in the SAME session. A directive that lives only in chat is a defect.
- **J-04 · Fail loud, not safe-silent.** A gate that "fails safe" by silently over-restricting still hides a
  defect. Under strict/CI mode, drift RAISES. (Lesson: search_policy silently became approval=True and hid a
  registry parse bug.)
- **J-05 · Honest deferrals.** Unfinished work is filed as an explicit P0/P1 with reproduce steps, not hidden
  or hand-waved. "NOT-CODE-COMPLETE — honestly" beats a preserved green. (Lesson: aifw-ios harness audit.)
- **J-06 · Security must be STRUCTURAL, not a soft boost.** Tenant/clearance isolation is a filter applied
  BEFORE ranking, so it can't be out-ranked. PII redaction runs on EVERY egress path incl. fallback branches.
- **J-07 · Side effects need a human.** Any tool that writes/acts is approval-gated (HITL). Unknown tool ->
  approval by default. "Agent proposes, human disposes."
- **J-08 · One source of truth per fact.** Derived files (registries, configs) are REGENERATED from the
  schema by an update script + drift-checked; never hand-edited in two places.
- **J-09 · Evals are the spec.** Write the golden set (incl. adversarial rows) BEFORE the code. Deterministic
  scorers at 1.0 are invariants; judges are thresholded AND measured against each other (agreement +
  calibration). Never pass on missing rows. Gate runs offline from a committed results file.
- **J-10 · Cheapest rung first.** prompt -> retrieval -> tools -> model swap -> fine-tune. Move a rung only
  when the previous plateaus ON THE EVALS. Most "custom model" asks are retrieval problems in disguise.

## SESSION HYGIENE
- **J-12 · Structured logging, always — never print, never guess.** Every model call, guard decision,
  tool call, and error emits a structured log (structlog JSON) with FULL context and FULL error text
  (never truncated). The log is the evidence. structlog for app logs; LangSmith for the agent trace.
  When something fails, read the log — don't theorize. (Lesson: a truncated 'Converse operatio...' error
  hid the real cause — 'use case form not submitted' — for two debug cycles.)
- **J-11 · Increment every download filename** (gate_v2.py, gate_v3.py, harness_v2.py…). A cleared or
  messy Downloads folder must never cause a stale copy to overwrite newer work. Never reuse a filename.
- Reattach git via remote, never lose history: `git init` + `git remote add` + `git fetch` + `git reset --soft origin/main` (keeps files).
- Secrets ONLY in local .env (gitignored). Private notes in .local/ (gitignored) or a private repo. Never paste keys to chat.
- Verify with `git ls-files | grep -i secret\|handoff` before every push.

## WHAT "5-STAR AGENT" MEANS (the FDE bar)
guard(PII+injection) -> plan -> act<->tools -> [HITL] -> finalize(schema+grounding+egress PII), traced,
scored, governed. 3 memory kinds. Routed multi-tenant retrieval w/ clearance tiers. Model registry
(open+closed, residency-driven) + fine-tune path. Audit report generated from real evidence. Every layer
a tested invariant. The reusability story: any new problem = fill 4 slots (golden set, corpus, tools,
output contract), everything else untouched.

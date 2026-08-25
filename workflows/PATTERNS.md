# Workflow patterns — the FDE framing

How to decompose a new enterprise problem into workflows, then attach tools + controls per step by risk.
Grounded in Anthropic's *Building Effective Agents* and mapped to THIS repo's real graph (`agent/graph.py`).

## 1 · Workflow vs. agent (the base distinction)
- **Workflow** — the path is **known before execution**: a predefined sequence of steps (LLM calls +
  tools) wired in a fixed shape. Predictable, cheap, testable.
- **Agent** — the path is **determined dynamically at runtime**: the model plans, acts, observes the
  result, and adjusts, looping until done. Flexible, but needs bounding (budgets, approvals, traces).

Enterprises use **both**, usually nested: a mostly-fixed workflow with one dynamic agentic step inside it,
or a dynamic agent whose individual steps are small fixed workflows. Start with the simplest thing that
works; add agency only where the path genuinely can't be known ahead of time.

## 2 · The five canonical patterns
| Pattern | One line | Use when |
|---|---|---|
| **Prompt-chaining** | fixed ordered steps, each feeds the next | the path is known & linear |
| **Routing** | classify the input, send it to the right specialized path | request types differ |
| **Parallelization** | run independent subtasks at once, then combine (sectioning or voting) | speed, or cross-checking |
| **Orchestrator-workers** | a lead decomposes the task, delegates to workers, assembles results | subtasks aren't known until runtime |
| **Evaluator-optimizer** | a producer + a critic loop until output meets a standard | quality is iterative / checkable |

## 3 · The determination method (how to pick a pattern for a NEW problem)
A decision procedure, not a menu. Run it top-down:

**a. Is the path known before starting, or does it depend on findings?**
   - Known ahead → it's a **workflow** (go to b).
   - Depends on what you discover mid-task → it's a **dynamic agent** (go to c).

**b. If the path is known — what shape?**
   - One thing after another → **prompt-chaining**.
   - It splits by request *type* → **routing**.
   - Independent pieces with no ordering between them → **parallelization** (for speed, or run the same
     input N ways and vote for reliability).

**c. If the path is dynamic — how does the agent make progress?**
   - It must break the task into sub-tasks it can't enumerate up front, then farm them out and reassemble
     → **orchestrator-workers**.
   - It produces a draft and improves it against a checkable standard → **evaluator-optimizer**.

**d. THEN, per step, ask: "what must-not-go-wrong here?"** — the answer attaches the TOOLS and CONTROLS:
   - a step that **acts** (side effect, blast radius) → an **approval gate** (HITL) + deterministic authz.
   - a step that **retrieves** customer data → **tenant/clearance filter before ranking** + injection-inert
     (retrieved text is data, not instructions).
   - a step that **answers** → **grounding** (citations ⊆ retrieved ids; confidence capped when ungrounded)
     + egress PII redaction.

> **The plain statement:** the workflow gives the **shape** (a–c); the **risk-per-step** gives the
> **controls** (d). A fresh enterprise problem is first decomposed into a workflow of steps, then each step
> gets exactly the tools and guards its worst case demands — nothing more, nothing less. The shape is a
> design choice; the controls are non-negotiable per the step's risk.

## 4 · This agent's real flows → patterns (grounded in `agent/graph.py`)
The wiring: `START → guard_input → plan → act ⇄ tools → [approval] → finalize → END`, with three
conditional routers. Each real flow, its pattern, and the one-line WHY (per §3):

| Real flow (files) | Pattern | Why (the determination) |
|---|---|---|
| **Read / answer path** — `guard_input → plan → act → finalize` (`route_after_guard`→plan; `route_after_act`→finalize when the model proposed no side effect) | **prompt-chaining** | The path for a read is known & linear (§a→§b): guard-scrub → plan → answer → ground. A `search_kb` call is a bounded retrieval sub-step; step-risk (§d) attaches tenant filter + grounding, no approval. |
| **The three routers** — `route_after_guard` / `route_after_act` / `route_after_approval` (`graph.py:133-141`) | **routing** | The next node depends on the *type* of state (§b): a refusal short-circuits to finalize; a plain answer finalizes; a **side-effect** proposal is sent to the approval path. Classify → dispatch. |
| **Act ⇄ tools loop** — `plan → act → tools → act …` bounded by `budget_guard` (`act:58`, `traced_tools:145`) | **dynamic agent** (ReAct) | The path *depends on findings* (§a→§c): the model acts, observes the tool result, and adjusts until done. Not a fixed sequence — hence bounded by a step/tool budget and fully traced. |
| **Action / approval path** — `act` (proposes side effect) → `approval` (HITL interrupt) → `tools` (execute approved-hash only) → `finalize` (`approval:82`, `traced_tools`) | **evaluator-optimizer** *(gate flavor)* + chaining | The acting step's must-not-go-wrong is blast radius (§d) → the **human is the evaluator**: the agent *proposes*, the human *disposes* against the "authorized + exactly-what-was-approved" standard; only a hash-matched call executes (unapproved/mutated → REFUSED). |
| **Agent-to-agent** — `A2ACaller.run_task`: `POST /run` → on `interrupt`, hand the proposal to `approval_channel` → `POST /approve` echoing the seen hashes → repeat ≤ `MAX_APPROVAL_ROUNDS` (`agent/a2a.py`) | **prompt-chaining across a boundary** + propagated gate | A caller's steps are known & linear (§b), but it has **no approval authority**: the HITL gate is a control that rides across the A2A boundary (§d) — the interrupt propagates and only its channel can release it. |
| **Evals / model bake-off** — same golden set run per model, then `evals/gate.py` blocks on any invariant regression (`scripts/bakeoff.py`, `evals/harness.py`, `evals/gate.py`) | **parallelization** + **evaluator-optimizer** | Independent runs (per-model, per-case) with no ordering (§b) — run then compare/vote; the **gate is the critic** (§c): deterministic invariants must read 1.00, judges are thresholded — the run only "passes" against that standard. |

**Takeaway:** this agent is a **dynamic ReAct core** (act⇄tools) wrapped in **workflow-shaped** scaffolding —
routing at the branches, a chained read path, and an evaluator-style human gate on anything that acts. The
shape came from "is the path known?"; every control came from "what must not go wrong at this step?"

# Workflow patterns — the FDE framing

How to decompose a new enterprise problem into workflows, then attach tools + controls per step by risk.
Grounded in Anthropic's *Building Effective Agents* and mapped to THIS repo's real graph (`agent/graph.py`).
This is **method** — it is domain-agnostic. A new engagement keeps it verbatim and only declares which
flows it has (see `workflows/*.yaml` + `workflows/templates/`).

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

## 4 · This frame's real flows → patterns (grounded in `agent/graph.py`)
The wiring: `START → guard_input → plan → act ⇄ tools → [approval] → finalize → END`, with three
conditional routers (`route_after_guard` / `route_after_act` / `route_after_approval`). The flows below are
the **frame's** structural flows — they exist in every domain, using the frame's generic tools
(`search_kb` read, `submit_action` approval-gated). A domain re-instantiates them with its own tools; the
shape and the controls don't change.

| Frame flow (nodes) | Pattern | Why (the determination) |
|---|---|---|
| **Read / answer** — `guard_input → plan → act → finalize` (`route_after_act`→finalize when the model proposed no side effect) | **prompt-chaining** | The read path is known & linear (§a→§b): guard-scrub → plan → answer → ground. A `search_kb` call is a bounded retrieval sub-step; step-risk (§d) attaches tenant filter + grounding, no approval. |
| **The three routers** — `route_after_guard` / `route_after_act` / `route_after_approval` | **routing** | The next node depends on the *type* of state (§b): a refusal short-circuits to finalize; a plain answer finalizes; a **side-effect** proposal is sent to the approval path. Classify → dispatch. |
| **Act ⇄ tools loop** — `plan → act → tools → act …` bounded by the step/tool budget | **dynamic agent** (ReAct) | The path *depends on findings* (§a→§c): the model acts, observes the tool result, and adjusts until done. Not a fixed sequence — hence bounded by a budget and fully traced. |
| **Action / approval** — `act` (proposes a side effect) → `approval` (HITL interrupt) → `tools` (execute approved-hash only) → `finalize` | **evaluator-optimizer** *(gate flavor)* + chaining | The acting step's must-not-go-wrong is blast radius (§d) → the **human is the evaluator**: the agent *proposes*, the human *disposes* against the "authorized + exactly-what-was-approved" standard; only a hash-matched call executes (unapproved/mutated → REFUSED). |
| **Agent-to-agent** — a caller `POST /run`s; on `interrupt` it hands the proposal to its approval_channel, then `POST /approve`s echoing the seen hashes (`agent/a2a.py`) | **prompt-chaining across a boundary** + propagated gate | A caller's steps are known & linear (§b), but it has **no approval authority**: the HITL gate is a control that rides across the A2A boundary (§d) — the interrupt propagates and only its channel can release it. |
| **Evals / gate** — the golden set is scored, then `evals/gate.py` blocks on any invariant regression (`evals/runner.py`, `evals/gate.py`) | **parallelization** + **evaluator-optimizer** | Independent per-case runs with no ordering (§b) — run then compare; the **gate is the critic** (§c): deterministic invariants must read 1.00, judges are thresholded — the run only "passes" against that standard. |

**Takeaway:** this frame is a **dynamic ReAct core** (act⇄tools) wrapped in **workflow-shaped**
scaffolding — routing at the branches, a chained read path, and an evaluator-style human gate on anything
that acts. The shape came from "is the path known?"; every control came from "what must not go wrong at
this step?"

## 5 · Declaring your domain's flows
`workflows/*.yaml` declares each flow this engagement actually has: its business request, its pattern (from
§2, or `dynamic-agent`), its ordered steps (real graph nodes), the tools each step uses (from the registry),
and the controls each step carries (`D-###` rows in `MANIFEST.md`). Start from
`workflows/templates/domain-flow.template.yaml` — copy it, fill the `SLOT` markers, drop the file in
`workflows/`. `python -m presentation.build_workflows` (and `make showcase`) renders them behind
`/workflows`, led by the determination method above. `tests/test_workflows.py` fails if a flow names a tool
not in the registry, a control not in the MANIFEST, or an unknown pattern.

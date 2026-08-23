# DEMO RUNBOOK — the two-terminal governed-agent demo

What it shows: the model reasons freely, but every side effect crosses a **human approval gate that
binds to the exact proposal** (D-034/D-038) — through a chat UI, and unchanged when **another agent**
initiates (D-040). Total time: ~6 minutes. Everything below is real: real graph, real guards, real
approval hashes; nothing is staged.

## Setup (once, before going on screen)

```bash
bash demo.sh          # or: make demo
```

`demo.sh` refuses to start unless the environment is demo-safe: `.env` has `ANTHROPIC_API_KEY`
(the server does not read `.env` itself — the script sources it), `DEMO_AUTOAPPROVE` is forced OFF
(it would bypass the gate the demo exists to show), the principal is `alice@meridian` (so a self
`reset_access(alice)` passes the deterministic authz layer, D-033), and port 8000 is free.

## Beat 1 — chat UI: agent proposes, human disposes (~3 min)

Open **http://localhost:8000/**. Type (naming the employee keeps the model's args deterministic —
a vaguer ask can make it pass `employee_id: "self"`, which the authz layer then denies; that's a fine
*layered* demo but a messier first beat):

> This is alice. I am locked out of the vpn — please reset vpn access for employee alice.

| You see | Say |
|---|---|
| **Amber approval card**: `reset_access({"employee_id": "alice", "system": "vpn"})` + sha256 **proposal hashes** (the model may batch a `lookup_employee` read alongside — reads carry no hash, only the side effect binds) | "The model decided; the *graph* stopped it. I'm not approving 'yes' — I'm approving these hashes: sha256 of tool, normalized args, principal, tenant, run. Approve alice, and if anything mutates it to bob before execution, the hash mismatch refuses it. That's a tested invariant, not a UI promise." |
| Answer with `status: queued` + **trace chips** `guard_input → plan → act → approval → tools[reset_access] → …` | "Every response carries its node path — the trace is the evidence, and the same path lands in LangSmith." |
| Ask the same thing again on the SAME thread, approve again → **idempotent skip** | "Approved once means executed at most once — a replayed approval is a recorded no-op, not a second reset." |
| Click **Deny** on a fresh proposal → "Denied by human", nothing executed | "Deny is a first-class outcome, not an error." |

**Multi-turn (same thread — D-041).** Threads are conversational: tell it *"my badge number is 7741"*,
then ask *"what badge number did I give you?"* — it answers from the thread history (the system prompt
is bound per model call, never persisted, so turns can't corrupt the message contract). And if you type
a new message **while an approval card is pending**, the agent refuses to move on — it returns the SAME
undecided proposal (`status: pending_approval`): *"you can't talk past a pending approval; a human
decision is a blocking step, not a suggestion."*

## Beat 2 — A2A: another agent initiates, the gate holds (~2 min)

Terminal 2:

```bash
.venv/bin/python scripts/a2a_demo.py "This is alice. I am locked out of the vpn - please reset vpn access for employee alice."
```

A *calling agent* delegates the task over the same HTTP contract. The console prints
`=== APPROVAL REQUIRED (agent-initiated) ===` with the pending call + hashes and waits for **y/N** —
the calling agent has no approval authority; its only path past the interrupt is its approval
channel (a human here; an explicit `policy_channel` allowlist in code). Say: *"Governance is
transport-independent — human-initiated or agent-initiated, privileged actions cross the same human
gate. And the governed graph is deliberately not exposed over MCP: stdio can't round-trip the
interrupt, so it would hang or force auto-approve. Read-only tools are what MCP publishes."*

## Beat 3 — the proof, if asked (~1 min)

```bash
.venv/bin/python -m pytest tests/test_api_hitl.py tests/test_a2a.py -v   # 8 wire-level guards
.venv/bin/python update.py --check                                       # the full gate, 135 green
```

`tests/test_api_hitl.py::test_approval_binds_to_what_the_human_saw` is the tamper test: approve
alice's hashes, mutate the pending state to bob, bob never runs.

## Reset between takes

- **Fresh proposal**: click **new thread** in the UI (fresh `thread_id` = fresh `run_id` = fresh
  hashes); `a2a_demo.py` generates a fresh thread every invocation. No server work needed. Staying on
  the same thread is also fine — that's the multi-turn beat; just remember a re-approved identical
  action is an idempotent skip by design.
- **Full reset**: Ctrl-C and rerun `demo.sh` — the checkpointer (`MemorySaver`) and approval/executed
  sets are in-process, so a restart wipes everything.
- Long-term memory only persists if a `remember` proposal was *approved* (`.local/memory.json` —
  delete it to forget).

## What production would add (one-liners)

1. **Identity**: the principal comes from the gateway's verified IdP token (OIDC/JWT sig/iss/aud/exp),
   not env vars — this repo enforces *inside* that trust boundary (D-033), including who may call `/approve`.
2. **Audit**: LangSmith is observability; a regulated deployment adds an append-only, retained record
   of who-approved-which-hash-when — a durable store, not a tracing dashboard.
3. **MCP**: stays read-only (D-025) — the governed graph is never published over MCP because stdio
   cannot round-trip the approval interrupt; agent callers use the HTTP contract (D-040).
4. **Data-egress control**: side effects are HITL-gated (a human sees the action before it fires), but
   there is no **destination allowlist / DLP** on tool args yet — an approved tool could in principle
   send data anywhere. Production adds a DLP layer (see `docs/HARDENING-BACKLOG.md`, Integration plane).

The full red-team posture — proven invariants, fixes, and scoped gaps by severity — is in
[`docs/HARDENING-BACKLOG.md`](HARDENING-BACKLOG.md).

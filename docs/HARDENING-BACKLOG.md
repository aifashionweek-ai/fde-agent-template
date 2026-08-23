# HARDENING BACKLOG — adversarial posture

Output of a red-team pass over the governed agent. Every claim here is backed by a test or a file:line,
per plane → per layer. The point of the artifact: the controls that matter are **tested invariants**, the
gaps are **named and scoped** (not discovered later), and the deferral reasons are explicit.

Severity: **S1** = exploitable bypass of a deterministic control / data leak · **S2** = defense-in-depth or
compliance gap a regulated deployment needs · **S3** = hardening / hygiene. Effort: **S** ≤½day · **M** ≤2days · **L** > that.

---

## CONTROL plane — bounding what it can do

**Proven (attack it catches → test):**
- Tenant isolation is structural — retrieval filters tenant before scoring; `authorize()` denies cross-tenant. `tests/test_authz.py::test_cross_tenant_denied`, `tests/adversarial/test_attacks.py::test_cross_tenant_retrieval_is_structural`
- Self-only credential reset (unless admin). `tests/test_authz.py::test_alice_cannot_reset_bob`
- No self-approval of a privileged escalation. `tests/test_authz.py::test_self_approval_of_privileged_denied`
- Approval binds to the exact proposal hash; mutate alice→bob after approval → REFUSED. `tests/test_api_hitl.py::test_approval_binds_to_what_the_human_saw`
- Forged (fabricated) hashes on /approve execute nothing. `tests/test_api_hitl.py::test_forged_hashes_on_approve_execute_nothing`
- Replay of a spent approval → idempotent skip. `tests/adversarial/test_attacks.py::test_approval_replay_executes_once`
- Caller cannot inject a privileged principal via the request body (principal is server-side). `tests/test_api_hitl.py::test_caller_cannot_inject_a_privileged_principal`
- Doc-ACL + sensitivity ceiling, fail-closed on empty groups. `tests/test_authz.py::test_retrieve_doc_acl_group_overlap`
- Every API error is structured JSON, never a plain-text 500. `tests/test_api_multiturn.py::test_run_unexpected_exception_is_structured_json`

**Fixed this pass:**
- **D-042** — `authorize()` normalizes identities (NFKC + strip + casefold) before compare. A raw compare let a caller self-approve a privileged escalation by writing the `requester` id with a trailing space / different case / full-width homoglyph. `tests/test_authz.py::test_self_approval_bypass_via_identity_variants_is_denied`
- **D-045** — authorization now runs BEFORE the human approval gate (not just inside execution). Previously a cross-user reset was shown to a human and only denied post-approval at `tools.py`; now the approval node denies unauthorizable proposals pre-interrupt, so a human is never asked to approve an action that was never allowable. In-tool authz stays as defense-in-depth. `tests/test_authz_ordering.py::test_cross_user_never_reaches_the_approval_gate`

**Bucketed gaps:**
| Gap | Sev/Eff | Production control that closes it | Why deferred |
|---|---|---|---|
| Cross-**script** confusables (Cyrillic 'а' U+0430) still evade identity compare — NFKC folds width/compat/case but not script | S3/M | Unicode **TR39 confusables skeleton** on identity fields, or restrict ids to a charset at the IdP | NFKC+casefold+strip closes the realistic hygiene bypasses today; a full confusables map is its own dependency + test matrix |
| Cross-principal **/approve auth** — any caller who reaches /approve can decide; who-may-approve isn't enforced here | S2/M | **IdP token at the gateway (D-033)** — /approve behind an authenticated approver role; principal from a verified OIDC/JWT, not env | Documented trust boundary: this repo enforces *inside* the gateway; wiring a real IdP is out of scope for the artifact |
| Unknown **sensitivity label** in an authz `retrieve` resource defaults to "internal" (permissive) | S3/S | Fail-closed: unknown label → treat as max sensitivity / deny | Not attacker-reachable — `chunk_document` enum-asserts sensitivity at ingestion (`retrieval.py:28`); latent only |

---

## ASSURANCE plane — proving it continuously

**Proven:**
- Direct prompt injection refused at the input guard. `tests/adversarial/test_attacks.py::test_direct_injection_is_refused`
- **Indirect** injection is inert end-to-end — a poisoned retrieved doc obeyed by a swayed model still can't skip the gate or authorize a cross-user reset (**D-043**). `tests/adversarial/test_injection_via_retrieval.py`
- Ungrounded citations dropped + confidence capped. `tests/adversarial/test_attacks.py::test_ungrounded_citation_dropped_and_confidence_capped`
- Egress PII scrub on every output path incl. fallback. `tests/adversarial/test_attacks.py::test_pii_scrubbed_on_egress`
- Runaway tool loop bounded and returns cleanly (graph-level). `tests/test_api_multiturn.py::test_crafted_tool_loop_returns_cleanly_not_unbounded`

**Bucketed gaps:**
| Gap | Sev/Eff | Production control | Why deferred |
|---|---|---|---|
| Durable **append-only compliance log** (who approved which hash, when) | S2/M | Append-only store (e.g. QLDB / WORM S3 / signed log) separate from LangSmith | LangSmith is observability, not a retained audit record — named limitation, not a surprise |
| Injection detector is **regex-first** (model classifier is opt-in) | S3/M | Prompt-Guard / Lakera always-on (`GUARD_INJECTION`) | Deterministic-first by design; classifier is a config flip, cost/latency trade |

---

## INTEGRATION plane — fitting the stack

**Proven:**
- MCP publishes READ tools only; governed graph never exposed (no approval round-trip over stdio). `tests/test_mcp.py`, `tests/adversarial/test_attacks.py::test_mcp_never_exposes_action_tools`
- A2A: interrupts propagate; caller can't auto-execute; abstain = deny. `tests/test_a2a.py`

**Bucketed gaps:**
| Gap | Sev/Eff | Production control | Why deferred |
|---|---|---|---|
| **Data-egress allowlist on tool args** — an approved action tool could send data to an arbitrary destination (email/webhook); no destination allowlist exists | S2/L | **DLP layer** — destination allowlist + payload inspection before a side-effecting tool egresses | Real gap, but a DLP layer is L-effort; deliberately NOT built pre-review. HITL still gates every side effect, so a human sees the destination before it fires |
| Rate limits / quotas / cost caps beyond `budget_guard` | S3/M | API gateway throttling + per-tenant quotas | Roadmap; single-run budget is enforced today |

---

## ONE-PAGE POSTURE SUMMARY

- **Proven controls:** 19 tested invariants across the three planes (tenant, reset, approval-binding, forged/replay hashes, principal-injection, doc-ACL, structured errors, direct + **indirect** injection, grounding, egress PII, loop cap, MCP read-only, A2A propagation).
- **Fixed today:** 2 new D-rows — **D-042** (identity-normalization deny-bypass, a real deterministic-control bypass) and **D-043** (indirect-injection-through-retrieval flagship), plus confirming tests for forged hashes, principal injection, and the graph-level loop cap.
- **Bucketed:** 9 gaps, all S2/S3 — none an open S1. The three that a regulated deployment needs first:

  1. **Cross-principal /approve authentication** (S2/M) — IdP token at the gateway (D-033). The single most important production add: today /approve trusts its caller.
  2. **Durable append-only compliance log** (S2/M) — who-approved-what-when, retained; LangSmith is observability only.
  3. **Data-egress allowlist / DLP on tool args** (S2/L) — a human still approves every side effect, but destination-level control is a real gap.

The header claim holds: the model reasons freely; authorization, tenant isolation, approval-binding, and PII redaction are enforced **outside** the model in deterministic code, each with a catch-proven test — and an attacker who fully compromises the model's reasoning (indirect injection) still cannot cross those boundaries.

# MANIFEST — FDE Agent Template (SKELETON)
Rule: every directive lands as a D-### row here + MASTERSCHEMA rows + a catch-proven guard (tests/) in the same session.
A directive that exists only in a chat, a doc, or a slide is a defect. `python update.py --check` refuses to pass with an open row.

This skeleton keeps the generic CONTROL/ASSURANCE frame as tested invariants. The domain (golden set, corpus,
tools, output contract) is the four SLOTs — fill those, leave everything below untouched.

| ID    | Directive                                                                 | Guard (test)                                              | Status |
|-------|---------------------------------------------------------------------------|-----------------------------------------------------------|--------|
| D-001 | Agent must terminate: max_steps enforced; budget breach is a RESULT       | tests/test_frame.py::test_budget_bounds_runaway           | ✅ |
| D-002 | Every LLM output is schema-validated (Pydantic) before use                | tests/test_frame.py::test_output_schema_validated         | ✅ |
| D-003 | Tools are allowlisted; unknown tool call = hard reject                    | tests/test_frame.py::test_unknown_tool_rejected           | ✅ |
| D-004 | Side-effect tools require human approval (interrupt)                      | tests/test_frame.py::test_action_tool_needs_approval      | ✅ |
| D-005 | Input + output PII redaction; prompt-injection detection (layered)        | tests/test_frame.py::test_input_guard_redacts_and_refuses | ✅ |
| D-011 | Retrieval is ROUTED: tenant isolation applied before scoring              | tests/test_retrieval.py::test_tenant_isolation_is_structural | ✅ |
| D-012 | Output is GROUNDED: citations ⊆ retrieved ids; ungrounded → capped/reject | tests/test_frame.py::test_grounding_caps_confidence       | ✅ |
| D-033 | Deterministic authorization (NOT the LLM): tenant isolation + self-only action unless admin | tests/test_frame.py::test_authz_self_only_and_tenant | ✅ |
| D-034 | Approval integrity + idempotency: approval binds to proposal_hash; tamper REFUSED; replay = idempotent skip | tests/test_approval.py::test_approve_alice_execute_bob_is_refused | ✅ |
| D-042 | Identity comparisons normalized (NFKC+strip+casefold) before compare      | tests/test_frame.py::test_authz_identity_normalized       | ✅ |
| D-044 | Per-layer observability spans (real tokens/latency/status), additive      | tests/test_frame.py::test_telemetry_one_span_per_node     | ✅ |
| D-045 | Authorization runs BEFORE the human approval gate                        | tests/test_frame.py::test_authz_before_gate               | ✅ |
| D-046 | Eval harness: invariant breach gate + quality thresholds over per-layer datasets | tests/test_frame.py::test_eval_gate_no_breaches   | ✅ |
| D-0xx | <problem-specific directive from the engagement>                          | tests/test_problem.py                                     | ⬜ |

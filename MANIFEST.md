# MANIFEST — FDE Agent Template
Rule: every directive lands as a D-### row here + MASTERSCHEMA rows + a catch-proven guard (tests/) in the same session.
A directive that exists only in a chat, a doc, or a slide is a defect. `python update.py --check` refuses to pass with an open row.

| ID    | Directive                                                                 | Guard (test)                                              | Status |
|-------|---------------------------------------------------------------------------|-----------------------------------------------------------|--------|
| D-001 | Agent must terminate: max_steps enforced via recursion_limit              | tests/test_guards.py::test_max_steps                      | ✅ |
| D-002 | Every LLM output is schema-validated (Pydantic) before use                | tests/test_guards.py::test_output_schema                  | ✅ |
| D-003 | Tools are allowlisted; unknown tool call = hard reject                    | tests/test_guards.py::test_tool_allowlist                 | ✅ |
| D-004 | Destructive/side-effect tools require human approval (interrupt)          | tests/test_guards.py::test_hitl_gate                      | ✅ |
| D-005 | Input + output PII redaction; prompt-injection detection (layered)        | tests/test_guards.py::test_input_guard, ::test_output_pii_redaction | ✅ |
| D-006 | Every run is traced (LangSmith) and scored (Braintrust)                   | evals/run_evals.py · agent/tracing.py                     | ✅ |
| D-007 | Cost/latency/tool-call budget per run; abort past budget                  | tests/test_guards.py::test_budget                         | ✅ |
| D-008 | Model is swappable via env (Anthropic / Bedrock / HF) behind one interface| agent/llm.py · agent/models.py                            | ✅ |
| D-009 | Model SELECTION is constraint-driven and deterministic (residency, cost, quality, task, license) | tests/test_models.py                 | ✅ |
| D-010 | Every retrieved chunk carries provenance (doc, source, tenant, sensitivity, time) | tests/test_retrieval.py::test_provenance_on_every_chunk | ✅ |
| D-011 | Retrieval is ROUTED: tenant isolation + sensitivity ceiling + source allow-list, applied before scoring | tests/test_retrieval.py::test_tenant_isolation_is_structural, ::test_sensitivity_ceiling, ::test_source_allowlist | ✅ |
| D-012 | Output is GROUNDED: citations ⊆ retrieved ids; ungrounded → capped confidence or reject | tests/test_guards.py::test_grounding_partial_caps_confidence, ::test_grounding_strict_mode, ::test_no_evidence_no_high_confidence | ✅ |
| D-013 | Every result carries its own trace path (node sequence); path must start at guard_input | tests/test_evals_meta.py::test_path_sane     | ✅ |
| D-014 | Eval confidence: calibration (ECE) + two-judge agreement + per-slice regression gate | tests/test_evals_meta.py · evals/gate.py     | ✅ |
| D-015 | Bedrock path uses inference-profile ids + Guardrails when configured; preflight script proves access | scripts/bedrock_preflight.sh · tests/test_models.py::test_residency_constraint | ✅ |
| D-016 | Long-term memory: facts persist across threads/sessions, injected as context, upsert by (scope,key), TTL | tests/test_memory.py::test_upsert_by_scope_key, ::test_recall_context_scoped, ::test_ttl_expiry | ✅ |
| D-017 | Memory is customer data: tenant+user isolation is structural, provenance recorded, right-to-be-forgotten | tests/test_memory.py::test_tenant_user_isolation_is_structural, ::test_forget_right_to_be_forgotten, ::test_provenance_recorded | ✅ |
| D-018 | Memory WRITES are side effects: remember/human_handoff gated through approval (HITL) | tests/test_guards.py::test_hitl_gate | ✅ |
| D-0xx | <problem-specific directive from the interview prompt>                    | tests/test_problem.py                                     | ⬜ |

# Architecture

```mermaid
flowchart LR
  C[Caller: UI · other agent · cron] --> A[FastAPI /run /approve /contract<br/>Lambda (SAM) or App Runner]
  A --> G[LangGraph agent]
  subgraph G[ ]
    direction LR
    gi[guard_input<br/>L0-L2 PII + injection] --> p[plan] --> act[act<br/>budget_guard]
    act -->|tool calls| t[ToolNode<br/>allowlist]
    t --> act
    act -->|side-effect tool| h[approval<br/>HITL interrupt] --> t
    act -->|answer| f[finalize<br/>schema + grounding + egress PII]
  end
  t --> R[(retrieval<br/>tenant · sensitivity · source<br/>BM25 + embeddings)]
  act --> M{model profile<br/>select_model}
  M --> M1[Anthropic API]
  M --> M2[Bedrock + Guardrails<br/>customer VPC]
  M --> M3[HF endpoint / vLLM<br/>self-hosted open weights]
  G -.traces, path, metadata.-> LS[LangSmith]
  G -.scored runs.-> BT[Braintrust + gate.py]
  MAN[MANIFEST D-### · MASTERSCHEMA · update.py --check --evals] -.governs.-> G
```

**Request path:** guard_input → plan → (act ⇄ tools, with approval on side effects) → finalize. Every node appends to `path`; the result carries `{path, steps, tool_calls}`.

**Data path:** documents land with provenance (tenant, source, sensitivity) → routed retrieval → chunk ids → the only legal citations → grounding check at finalize.

**Model path:** constraints (residency, cost, quality, task, license) → `select_model` → provider build; Bedrock gets Guardrails attached; HF gets the dedicated endpoint URL if present.

**Governance:** MANIFEST rows ↔ tests ↔ MASTERSCHEMA contracts; `update.py` regenerates the tool registry, checks drift (tools in code vs schema; D-rows vs test files), runs pytest, and optionally the Braintrust gate. A deploy can't pass with a red guard or a regressed slice.

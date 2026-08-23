# evals/ — the eval harness (harness C)

One entrypoint (`runner.py`) runs two kinds of check across per-layer datasets and emits one report.
The split mirrors the repo's thesis: **invariants are must-be-zero breach checks on the deterministic
controls; quality is graded 0..1 against explicit thresholds.** Any invariant breach fails the gate hard.

```
evals/
  datasets/    one .jsonl per layer/control — {input, expected_control_outcome, layer, attack_class, ...}
  scorers/
    invariant/ binary, deterministic breach scorers (authz, tenant, approval/hash, injection-inert, guard)
    quality/   graded 0..1 (retrieval recall@k, groundedness/citation-faithfulness) with thresholds
  runner.py    the entrypoint: invariant + quality across all datasets → report/ (JSON + human) + Braintrust
  report/      generated (git-ignored except report/sample.json)
  README.md    this file
  # legacy (row-per-run golden set + Braintrust): dataset.jsonl, harness.py, gate.py, run_evals.py, scorers/__init__.py
```

## Folder → plane → layer → Agent-SDK / MCP convention

| Dataset | Plane | Control it guards | D-row | SDK / MCP convention |
|---|---|---|---|---|
| `guard_input` | Control | input guard: injection/jailbreak/override refused; benign passes | D-005 | pre-model **input guardrail** (Agent-SDK input guard) |
| `authz` | Control | `authorize()`: self/cross-user/admin/clearance/doc-ACL + homoglyph/whitespace/case | D-033/D-042 | **tool-use authorization** — deterministic, before the tool runs |
| `tenant` | Control | tenant isolation: cross-tenant action denied; cross-tenant retrieval isolated | D-011 | multi-tenant **namespace isolation** (one MCP/vector namespace per tenant) |
| `approval_hash` | Control | approval binding: mutate/forged/replay → refused/skip; happy → execute | D-034/D-038 | **human-in-the-loop tool approval** with a bound proposal |
| `injection_inert` | Assurance | indirect (retrieval-borne) injection can't authorize a side effect | D-043/D-045 | **untrusted tool output** — retrieved content is data, not instructions |
| `retrieval_quality` | Intelligence | recall@k: routing surfaces the relevant chunks | D-010/D-011 | **RAG retrieval** quality (MCP resource / retrieval tool) |
| `groundedness` | Assurance | citation faithfulness: cites ⊆ retrieved; confident-no-evidence capped | D-012 | **output guardrail** (grounding / citation check) |
| `egress` | Integration | destination allowlist on tool args — **xfail (roadmap)** | — | **DLP on tool egress** (not built; HITL shows destination) |

## Running

```bash
make evals                       # runner: invariant gate + quality thresholds; exits nonzero on any breach
python -m evals.runner --quiet   # summary only
python -m evals.runner --braintrust   # also push graded quality history to Braintrust (needs key)
```

- **Invariant scorers reuse the same control code the graph uses** — a breach is a real regression, not a
  test artifact. They are deterministic and offline, so they run **in CI** (via a pytest wrapper) and gate.
- **Quality scorers here (recall@k, groundedness) are deterministic** and also run in CI.
- **Judge-based quality** (answer relevance, plan efficiency) is heavier and model-dependent → **Braintrust /
  nightly / manual**, not part of the CI gate. Token/latency sanity bounds come from real telemetry
  (self-reset ~3.4k tok, policy read ~7.4k, injection ~9.7k — see `evals/fixtures/telemetry_runs.json`).
- **xfail rows** are documented residuals (cross-script confusables, D-042; egress/DLP): run and reported,
  never hidden, never gating. An xfail that starts passing is surfaced as an xpass.

The per-layer observability dashboard (`GET /dashboard`, D-044) reads the real captured spans in
`evals/fixtures/telemetry_runs.json` — one dashboard, real data, no illustrative array.

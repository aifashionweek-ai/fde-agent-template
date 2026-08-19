# 06 · Tracing with LangSmith — seeing the path, not just the answer

## 1. Why AI-native tracing (and what bolt-ons miss)
Datadog/CloudWatch see HTTP spans. They don't see the **prompt**, the **tool calls and results**, **tokens/cost per step**, or the **node path** through the graph. LangSmith (or Langfuse self-hosted) does — that's the difference between "p95 is 4 s" and "the planner emitted 7 steps because the retrieved chunk was empty."

Two env vars, zero code: `LANGSMITH_TRACING=true LANGSMITH_API_KEY=…`. LangGraph spans every node automatically.

## 2. What this template adds (`agent/tracing.py`, D-013)
- **Run metadata** — `tenant`, `model_profile`, `git_sha`, `experiment` on every run; tags `tenant:<t>` `model:<p>`. Now you can filter traces per customer, per model, per deploy.
- **Path in the output** — `node_span` appends the node name to `state.path`; `run()` returns `trace.path` like `["guard_input","plan","act","tools","act","finalize"]`. The answer carries its own audit trail; `path_sane` scores it.
- **Trace → eval row** — `trace_to_eval_row(run_id, expected, tags)` turns a prod run into a golden row (docs/05 §5).

## 3. How to read a trace (what I look at, in order)
1. **Path** — did it go through `guard_input`? How many `act⇄tools` loops? Did `approval` fire?
2. **Inputs to `act`** — the exact messages the model saw. Most bugs are "the model never saw X."
3. **Tool I/O** — `search_kb` returned what ids? Were they cited? (grounding, D-012)
4. **Token & latency per span** — where the time/cost went; the planner is often the surprise.
5. **Metadata** — which model profile, which sha, which tenant.

## 4. Dashboards and alerts worth having on day 1
- p50/p95 latency and cost **per tenant** (tags make this a filter).
- Error rate by `errors[]` content (guard rejections vs tool failures vs schema failures).
- **Path histogram** — a new path shape appearing in prod is a leading indicator of a regression.
- Online evaluators: run `no_raw_pii` / `grounded` as LangSmith online evals on a sample of prod traces.
- Alert when `approval` rate spikes (users probing side effects) or when `confidence` distribution shifts.

## 5. Langfuse (when the customer needs self-hosted)
Same concepts (traces, spans, scores, datasets); OpenTelemetry-compatible; runs in their VPC on Postgres. Swap is config-level: wrap `graph.invoke` with the Langfuse callback handler. Keep the same metadata keys (MASTERSCHEMA §Tracing) so dashboards port.

## 6. Interview line
"Every result carries its path, tenant, model, and sha. I read traces top-down — path, inputs, tool I/O, tokens — and I turn the interesting ones into eval rows. Tracing isn't observability theater; it's how the golden set grows."

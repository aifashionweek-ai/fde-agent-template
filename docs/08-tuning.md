# 08 · Tuning the agent on customer data — the ladder, the loop, the guardrails

## 1. The ladder (cheapest, most reversible first)
1. **Prompt** — system rules, output contract, few-shot from the golden set. Minutes.
2. **Retrieval** — chunking, hybrid scoring, reranker (bge-reranker / Cohere), metadata filters, parent-chunk expansion. Hours. *Most "tuning" requests end here.*
3. **Tools & contract** — give the agent a better tool (a SQL view, a typed API) instead of asking the model to infer. Hours–days.
4. **Model** — swap profile (docs/01), run the gate.
5. **Fine-tune** — LoRA/QLoRA on an open model (or provider fine-tuning where offered) on *the customer's labeled slice*, for a narrow, high-volume task. Days + ops. Only when 1–4 plateau **on the evals**.

Rule: move a rung only when the previous rung's best experiment fails the gate on the slice you care about.

## 2. The loop (one change per experiment)
baseline → failures by slice → hypothesis → one change → `EXPERIMENT=vN` → `gate vN baseline` → keep/revert → CHANGELOG. Each experiment in Braintrust carries `model_profile`, `guard_*`, git sha in metadata, so "what changed" is never a mystery.

## 3. Tuning on customer data — what's allowed
- Few-shot and retrieval use customer data at **inference** — same residency rules as the rest (docs/03 §5).
- Fine-tuning **trains** on it: needs a DPA clause that permits it, PII removed, and a **held-out** slice that never touches training. Provider fine-tuning (Bedrock custom models, OpenAI FT) keeps weights in the provider; open-weights FT keeps them with the customer.
- Never fine-tune on traces that contain other tenants' data.

## 4. Drift and re-tuning
- Model version bumps → rerun the gate before adopting.
- Corpus changes (new policies, products) → re-embed affected docs, rerun `grounding`/`kb` slices.
- Monitor the **path histogram** and **confidence distribution** in LangSmith (docs/06 §4); shifts trigger an eval run.

## 5. Interview line
"Tuning is eval-driven and ladder-ordered: prompt, retrieval, tools, model, then fine-tune — one change per experiment, gated per slice. Most customer problems are retrieval problems wearing a fine-tuning costume."

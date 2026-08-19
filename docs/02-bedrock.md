# 02 · Amazon Bedrock — when, why, and the enablement gates that eat the clock

## 1. When Bedrock earns its place
Bedrock is not "AWS's LLM API" — it's *the same frontier models with the customer's IAM, VPC, CloudTrail, and KMS wrapped around them*. Use it when the customer needs **model traffic to stay inside their AWS account**: regulated data (HIPAA BAA, PCI), PrivateLink-only egress, CloudTrail audit of every invoke, KMS-encrypted logs, or procurement that already has AWS on contract and won't onboard another vendor. If none of those apply, a direct API key is faster and cheaper to operate.

## 2. The gates (each one looks like an IAM error and isn't)
| # | Gate | Symptom | Fix |
|---|---|---|---|
| 1 | **Model access** is per-account *and* per-region | `ResourceNotFoundException` / model "not available" | Console → Bedrock → Model access → request; Anthropic models need the use-case form once |
| 2 | **Inference profile id** for newer Claude | `ValidationException: on-demand throughput isn't supported` | Use `us.anthropic.claude-…` (cross-region profile), not the bare `anthropic.claude-…` id |
| 3 | Region availability | model simply absent from `list-foundation-models` | us-west-2 / us-east-1 first; EU = `eu.*` profiles |
| 4 | IAM | `AccessDeniedException` | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`, plus `bedrock:ApplyGuardrail` if using Guardrails |
| 5 | Local creds ≠ target account | everything "works" in the wrong account | `aws sts get-caller-identity` first, always |
| 6 | Throughput | throttling at demo time | on-demand is fine for a demo; provisioned throughput is a procurement conversation |

`scripts/bedrock_preflight.sh` proves all of these in 30 seconds. **Run it the night before.** If it fails, Bedrock is a talking point tomorrow, not a build path — switch `MODEL_PROFILE=claude-sonnet-api`.

## 3. Wiring in this template
- `agent/models.py` → profile `claude-sonnet-bedrock` uses `ChatBedrockConverse` (the Converse API is the one that does tool-use uniformly across providers).
- `deploy/template.yaml` → `LlmProvider=bedrock` grants the invoke policy to the Lambda role; no keys anywhere.
- `DATA_RESIDENCY=customer_vpc` makes `select_model` refuse any vendor_api profile — the constraint is enforced, not remembered.

## 4. Bedrock Guardrails (L3 in our guard stack)
Create one in the console (content filters, denied topics, PII anonymize, contextual grounding check) → set `BEDROCK_GUARDRAIL_ID` / `BEDROCK_GUARDRAIL_VERSION`. `models.py` attaches it to every Converse call with `trace=enabled`, so guardrail interventions show up in the response and in LangSmith. It *complements* our L0/L4 guards — it can't see tool calls or citations, we can't see the customer's corporate denied-topic list; both run.

## 5. Cost & ops notes worth saying out loud
- Same model, Bedrock is usually priced at parity with the vendor API; you're paying for the boundary, not the tokens.
- Cross-region inference profiles route to sibling regions under load — if the customer has a strict single-region requirement, say so *before* choosing `us.*`.
- CloudTrail logs the invoke, **not** the prompt; enable **Model invocation logging** (S3/CloudWatch) if they need prompt-level audit — and then PII redaction before the model matters even more (D-005).

## 6. Interview line
"Bedrock is a boundary, not a model. I use it when the customer's data can't leave their account, and I burn the four enablement gates before the engagement starts — model access, inference-profile ids, IAM, region — because each one fails with a message that looks like something else."

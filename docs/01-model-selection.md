# 01 · Model selection — open weights vs closed weights, and how to decide

**The rule:** you don't pick a model, you pick a *profile* that satisfies constraints, then let evals rank the survivors. `agent/models.py` encodes this: `select_model(task_class, residency, max_cost_tier, min_quality_tier, prefer_open)`. It's deterministic and tested (D-009).

## 1. The four constraints that decide before quality does
| Constraint | Question to ask the customer | Forces |
|---|---|---|
| **Data residency** | Can prompts/completions leave your AWS account? | `vendor_api` (direct API) vs `customer_vpc` (Bedrock / Azure OpenAI / Vertex) vs `self_hosted` (open weights on their GPUs) |
| **License** | Will this be a product, and what's the revenue/MAU? | Llama community license (700M MAU clause), Apache-2.0 (Qwen, Mistral), Gemma terms — legal, not technical |
| **Cost ceiling** | $/1M tokens budget at expected volume | closed frontier at cost tier 3–5; 7–8B open at tier 1 |
| **Latency SLO** | p50/p95 TTFT and tokens/sec | small open models on a dedicated GPU beat any API on p95; APIs beat them on burst |

Only *after* those are fixed do you compare quality — **on your own golden set** (docs/05), never on vendor leaderboards.

## 2. Closed vs open — the honest trade-offs
| | Closed (Claude, GPT, Gemini) | Open weights (Llama, Qwen, Mistral, Gemma) |
|---|---|---|
| Frontier quality, long context, tool use | best | 70B+ competitive; 7–8B good for narrow tasks |
| Time to first useful result | minutes | hours–days (serving, quantization, eval) |
| Data control | contractual (DPA, zero-retention) or Bedrock in-VPC | total — weights and data never leave |
| Cost at scale | $/token, predictable | GPU hours; cheaper at sustained high volume, expensive at low |
| Fine-tuning | limited / hosted | full (LoRA/QLoRA/DPO) |
| Ops burden | none | model serving, autoscaling, upgrades are yours |
| When it wins | reasoning-heavy, agentic, unknown task mix, speed of delivery | narrow high-volume tasks (classification, extraction), strict residency, need to fine-tune |

**FDE default:** start closed-frontier via the cheapest *compliant* path (direct API → Bedrock if in-VPC required). Introduce open weights only for a *measured* reason: a slice where a fine-tuned 8B beats frontier on your evals, a cost line item, or a residency requirement that even Bedrock can't meet.

## 3. Where to get open-weights models and how to judge them
- **Hugging Face Hub** is the registry. Filter by task → license → size → recency. Read the model card for: training cutoff, context length, chat template, known failure modes, license.
- Check the **Open LLM Leaderboard** and **LMSYS Arena** for a *prior*, then **ignore them** and run your golden set. A model that's 2 points higher on MMLU and 10 points lower on your extraction slice is the wrong model.
- Quantization (AWQ/GPTQ/GGUF) changes quality — eval the *quantized* artifact you'll deploy, not the fp16 one.

## 4. Filling in the quality tiers (the honest way)
1. `EXPERIMENT=<profile> MODEL_PROFILE=<profile> make evals` for each candidate.
2. Read per-slice scores in Braintrust (not the average).
3. Set `quality_tier` in `REGISTRY` from *that*, commit the numbers in a `docs/model-eval-<date>.md` table.
4. Re-run quarterly or on any model version bump — tiers drift.

## 5. Open weights on Bedrock — selection, not deployment
Bedrock serves open-weight models (DeepSeek V3.2, Qwen3, Kimi K2.5, GLM, Mistral/Ministral, gpt-oss, Llama, Gemma…) serverlessly, per token, inside the customer account. You don't deploy them; you pick a model ID. SageMaker/Custom Model Import earn their place only for (a) a model not in the catalog or (b) your own fine-tuned weights. Tool use is supported on the 2025–26 wave (Llama 3.1+, Mistral Large, DeepSeek, Qwen3, Kimi…) — avoid the old ones (Llama 3, Mistral 7B/Mixtral). IDs and region availability vary: `aws bedrock list-foundation-models --region us-west-2 --by-output-modality TEXT --query 'modelSummaries[].modelId'` the night before, set the `BEDROCK_*_ID` envs, and `scripts/model_bakeoff.sh` turns the choice into a table.

## 6. Interview line
"I separate *can we use it* (residency, license, cost, latency) from *is it good* (our evals). The registry makes the first part a lookup and the second part a number we measured. Default is frontier-closed through the most compliant path; open weights earn their place per slice, on our data."

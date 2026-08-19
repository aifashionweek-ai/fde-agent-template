# 07 · Deploying open-weights models — Hugging Face Inference Endpoints, TGI/vLLM on your infra, SageMaker

## 1. Choose the deployment by who owns the GPU
| Option | Where it runs | Setup | Best for |
|---|---|---|---|
| **HF Serverless Inference** | HF shared | 0 min (token) | smoke tests, tiny volume; rate-limited, cold starts |
| **HF Inference Endpoints** (`deploy/hf_endpoint.py`) | HF-managed on AWS/GCP/Azure, your region | 10 min | dedicated GPU, autoscale, scale-to-zero, private link option; no cluster to run |
| **TGI / vLLM container on your infra** (EKS, ECS+GPU, App Runner can't) | customer's VPC | hours | strict residency, high sustained volume, custom quantization |
| **SageMaker real-time endpoint** (HF DLC / LMI) | customer's AWS | 30–60 min | AWS-native ops (IAM, VPC, autoscaling policies, CloudWatch), procurement already on AWS |
| **Bedrock (open models)** | AWS-managed | 5 min | Llama/Mistral on Bedrock with zero serving work — often the right answer for open weights on AWS |

Default for an FDE: **Bedrock for open models on AWS** (no serving), **HF Inference Endpoints** when you need a model Bedrock doesn't host, **vLLM/TGI on their cluster** only when residency or cost at scale forces it.

## 2. Sizing (rules of thumb)
- bf16 weights ≈ 2 bytes/param → 8B ≈ 16 GB, fits **L4 (24 GB)** / A10G; 70B ≈ 140 GB → needs 2×A100-80 or **4-bit quantization** (AWQ/GPTQ ≈ 0.5 B/param → 35 GB on one A100-80/H100).
- Add KV-cache headroom: longer context × batch = memory. Set `MAX_INPUT_LENGTH`/`MAX_TOTAL_TOKENS` deliberately.
- Throughput: vLLM/TGI continuous batching gives 5–10× single-request tokens/s; set `max_concurrent_requests`.

## 3. This template's path
```
HF_TOKEN=… python deploy/hf_endpoint.py meta-llama/Llama-3.1-8B-Instruct --gpu nvidia-l4 --min 0
export HF_ENDPOINT_URL=https://…endpoints.huggingface.cloud   # printed by the script
MODEL_PROFILE=llama-3.1-8b-hf make evals
```
`agent/models.py` uses `HF_ENDPOINT_URL` if set (dedicated), else serverless for `HF_MODEL_ID`. Scale-to-zero (`--min 0`) keeps the bill near zero between demos; first request after idle takes ~1 min.

## 4. Gotchas
- Gated models (Llama) need license acceptance on the Hub *and* a token with access.
- Chat template: `ChatHuggingFace` applies the model's template; a wrong template = garbage answers that look like a model problem.
- Tool calling on open models is uneven — keep the planner/tool-use on a frontier model and use the open model for the narrow task (classification/extraction) it was chosen for.
- Eval the quantized artifact you deploy (docs/01 §3).

## 5. Interview line
"I pick the serving path by who owns the GPU and how strict residency is: Bedrock if it hosts the model, HF Inference Endpoints for a dedicated GPU without a cluster, vLLM on their EKS when data or cost demands it. The agent doesn't know — it's a profile in the registry."

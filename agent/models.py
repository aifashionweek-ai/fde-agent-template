"""Model selection (D-008, D-009). One registry, one selector, three providers.

Why a registry and not an env var: an FDE chooses a model per *constraint set*
(data residency, cost ceiling, latency SLO, task class, license) — not by vibe.
The registry makes that choice explicit, auditable, and testable.

Usage:
    profile = select_model(task_class="reasoning", residency="customer_vpc")
    llm = profile.build(temperature=0)
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Literal, Optional

Provider   = Literal["anthropic", "bedrock", "hf"]
Weights    = Literal["closed", "open"]
Residency  = Literal["vendor_api", "customer_vpc", "self_hosted"]
TaskClass  = Literal["reasoning", "extraction", "classification", "summarization", "codegen"]

@dataclass(frozen=True)
class ModelProfile:
    id: str
    provider: Provider
    model: str                      # provider-specific id (for bedrock: inference-profile id, us.* prefix)
    weights: Weights
    residency: Residency
    cost_tier: int                  # 1 = cheapest … 5 = most expensive (rough $/1M out tokens bucket)
    latency_tier: int               # 1 = fastest … 5 = slowest (p50 TTFT bucket)
    quality_tier: int               # 1..5, from YOUR evals, not vendor claims (see docs/05-evals-braintrust.md)
    good_for: tuple[TaskClass, ...] = field(default_factory=tuple)
    context_k: int = 200
    license: str = "proprietary"    # open weights: "llama-3.x-community", "apache-2.0", "gemma", …
    notes: str = ""

    def build(self, temperature: float = 0.0, max_tokens: int = 2000):
        if self.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=self.model, temperature=temperature, max_tokens=max_tokens)
        if self.provider == "bedrock":
            from langchain_aws import ChatBedrockConverse
            return ChatBedrockConverse(model=self.model, region_name=os.getenv("AWS_REGION", "us-west-2"),
                                       temperature=temperature, max_tokens=max_tokens,
                                       guardrail_config=_bedrock_guardrail())
        if self.provider == "hf":
            from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
            ep = HuggingFaceEndpoint(endpoint_url=os.getenv("HF_ENDPOINT_URL") or None,
                                     repo_id=None if os.getenv("HF_ENDPOINT_URL") else self.model,
                                     temperature=max(temperature, 0.01), max_new_tokens=max_tokens)
            return ChatHuggingFace(llm=ep)
        raise ValueError(self.provider)

def _bedrock_guardrail() -> Optional[dict]:
    gid = os.getenv("BEDROCK_GUARDRAIL_ID")
    return {"guardrailIdentifier": gid, "guardrailVersion": os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
            "trace": "enabled"} if gid else None

# ---- Registry. Tiers are placeholders until YOUR eval run fills them in (docs/01-model-selection.md §4). ----
REGISTRY: dict[str, ModelProfile] = {p.id: p for p in [
    ModelProfile("claude-sonnet-api", "anthropic", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                 "closed", "vendor_api", cost_tier=3, latency_tier=2, quality_tier=5,
                 good_for=("reasoning","extraction","summarization","codegen"), notes="default; direct key"),
    ModelProfile("claude-haiku-api", "anthropic", "claude-haiku-4-5", "closed", "vendor_api",
                 cost_tier=1, latency_tier=1, quality_tier=3, good_for=("classification","extraction")),
    ModelProfile("claude-sonnet-bedrock", "bedrock",
                 os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
                 "closed", "customer_vpc", cost_tier=3, latency_tier=2, quality_tier=5,
                 good_for=("reasoning","extraction","summarization","codegen"),
                 notes="traffic stays in customer AWS acct; needs model access + inference profile (docs/02-bedrock.md)"),
    ModelProfile("llama-3.1-70b-bedrock", "bedrock", "us.meta.llama3-1-70b-instruct-v1:0",
                 "open", "customer_vpc", cost_tier=2, latency_tier=3, quality_tier=4,
                 good_for=("summarization","classification","extraction"), license="llama-3.1-community"),
    ModelProfile("llama-3.1-8b-hf", "hf", os.getenv("HF_MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct"),
                 "open", "self_hosted", cost_tier=1, latency_tier=2, quality_tier=2,
                 good_for=("classification","extraction"), license="llama-3.1-community",
                 notes="HF Inference Endpoint or TGI/vLLM on your GPU (docs/07-huggingface-deploy.md)"),
    ModelProfile("qwen2.5-7b-hf", "hf", "Qwen/Qwen2.5-7B-Instruct", "open", "self_hosted",
                 cost_tier=1, latency_tier=2, quality_tier=2, good_for=("classification","extraction","codegen"),
                 license="apache-2.0", notes="permissive license; strong small open model"),
]}

def select_model(task_class: TaskClass = "reasoning", residency: Optional[Residency] = None,
                 max_cost_tier: int = 5, min_quality_tier: int = 1, prefer_open: bool = False) -> ModelProfile:
    """Deterministic selection. Order: hard constraints → prefer_open → quality desc → cost asc → latency asc."""
    residency = residency or os.getenv("DATA_RESIDENCY") or None
    forced = os.getenv("MODEL_PROFILE")
    if forced: return REGISTRY[forced]
    cands = [p for p in REGISTRY.values()
             if (residency is None or p.residency == residency)
             and p.cost_tier <= max_cost_tier and p.quality_tier >= min_quality_tier
             and task_class in p.good_for]
    if not cands: raise LookupError(f"no model satisfies task={task_class} residency={residency} cost<={max_cost_tier} q>={min_quality_tier}")
    cands.sort(key=lambda p: ((p.weights != "open") if prefer_open else 0, -p.quality_tier, p.cost_tier, p.latency_tier))
    return cands[0]

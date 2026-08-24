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
from .logging_setup import log
from typing import Literal, Optional

Provider   = Literal["anthropic", "bedrock", "hf", "openai"]
Weights    = Literal["closed", "open"]


class MissingCredentials(RuntimeError):
    """A provider was selected but its API key isn't set. Raised (not returned) so a bare `build()` fails
    loud, but callers that want to SKIP a model (the bake-off) can catch this specific type and skip
    cleanly rather than crashing the whole run (J-04)."""
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
        log.info("model_build", profile=self.id, provider=self.provider, model=self.model,
                 weights=self.weights, residency=self.residency)
        if self.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=self.model, temperature=temperature, max_tokens=max_tokens)
        if self.provider == "bedrock":
            from langchain_aws import ChatBedrockConverse
            kwargs = dict(model_id=self.model, region_name=os.getenv("AWS_REGION", "us-west-2"),
                          temperature=temperature, max_tokens=max_tokens)
            gc = _bedrock_guardrail()
            if gc: kwargs["guardrail_config"] = gc
            # provider hint helps ChatBedrockConverse resolve inference-profile ids (us.*) correctly
            if "anthropic" in self.model: kwargs["provider"] = "anthropic"
            elif "meta" in self.model or "llama" in self.model: kwargs["provider"] = "meta"
            elif "qwen" in self.model: kwargs["provider"] = "qwen"
            return ChatBedrockConverse(**kwargs)
        if self.provider == "hf":
            from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
            ep = HuggingFaceEndpoint(endpoint_url=os.getenv("HF_ENDPOINT_URL") or None,
                                     repo_id=None if os.getenv("HF_ENDPOINT_URL") else self.model,
                                     temperature=max(temperature, 0.01), max_new_tokens=max_tokens)
            return ChatHuggingFace(llm=ep)
        if self.provider == "openai":
            # D-008: same one-interface swap. A missing key raises MissingCredentials (a clear one-line
            # message, caught by the bake-off to SKIP cleanly) — never a raw traceback / silent 1.00.
            if not os.getenv("OPENAI_API_KEY", "").strip():
                raise MissingCredentials("OPENAI_API_KEY not set — export OPENAI_API_KEY=sk-... to run gpt-4o")
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=self.model, temperature=temperature, max_tokens=max_tokens)
        raise ValueError(self.provider)

def _bedrock_guardrail() -> Optional[dict]:
    """Attach a Bedrock Guardrail ONLY if explicitly enabled with a real id. A missing/placeholder id
    must never be attached — an invalid guardrailIdentifier 400s the entire Converse call (this bug cost
    a whole bake-off: every open-model tool row failed with 'guardrail identifier is invalid' until the
    LangSmith trace revealed it was config, not the model). J-04: fail loud OR skip cleanly, never poison."""
    gid = os.getenv("BEDROCK_GUARDRAIL_ID", "").strip()
    if not gid or gid.lower() in ("none", "your-guardrail-id", "changeme", "placeholder"):
        return None
    # Bedrock guardrail ids are lowercase alphanumeric, ~12 chars. Reject obvious non-ids.
    if not gid.replace("-", "").isalnum():
        from .logging_setup import log
        log.warning("bedrock_guardrail_skipped", reason="id looks invalid", gid=gid)
        return None
    return {"guardrailIdentifier": gid, "guardrailVersion": os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
            "trace": "enabled"}

# ---- Registry. Tiers are placeholders until YOUR eval run fills them in (docs/01-model-selection.md §4). ----
REGISTRY: dict[str, ModelProfile] = {p.id: p for p in [
    ModelProfile("claude-sonnet-api", "anthropic", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                 "closed", "vendor_api", cost_tier=3, latency_tier=2, quality_tier=5,
                 good_for=("reasoning","extraction","summarization","codegen"), notes="default; direct key"),
    ModelProfile("claude-haiku-api", "anthropic", "claude-haiku-4-5", "closed", "vendor_api",
                 cost_tier=1, latency_tier=1, quality_tier=3, good_for=("classification","extraction")),
    ModelProfile("claude-sonnet-bedrock", "bedrock",
                 os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
                 "closed", "customer_vpc", cost_tier=3, latency_tier=2, quality_tier=5,
                 good_for=("reasoning","extraction","summarization","codegen"),
                 notes="traffic stays in customer AWS acct; needs model access + inference profile (docs/02-bedrock.md)"),
    ModelProfile("llama-3.1-70b-bedrock", "bedrock", "us.meta.llama3-1-70b-instruct-v1:0",
                 "open", "customer_vpc", cost_tier=2, latency_tier=3, quality_tier=4,
                 good_for=("summarization","classification","extraction"), license="llama-3.1-community"),
    # --- open weights SERVED BY BEDROCK (verified invoking in account 135359468175, us-west-2).
    #     Newer models require a cross-region inference profile id (us.* prefix), not the bare model id. ---
    ModelProfile("qwen3-32b-bedrock", "bedrock", os.getenv("BEDROCK_QWEN_ID", "qwen.qwen3-32b-v1:0"),
                 "open", "customer_vpc", cost_tier=2, latency_tier=3, quality_tier=4,
                 good_for=("reasoning","extraction","summarization","codegen"), license="apache-2.0",
                 notes="best all-round open model; clean license; verified QWEN-OK on Bedrock"),
    ModelProfile("llama-3.3-70b-bedrock", "bedrock", os.getenv("BEDROCK_LLAMA_ID", "us.meta.llama3-3-70b-instruct-v1:0"),
                 "open", "customer_vpc", cost_tier=2, latency_tier=3, quality_tier=4,
                 good_for=("reasoning","summarization","extraction"), license="llama-3.3-community",
                 notes="most-deployed open model; needs us.* inference profile; verified LLAMA-OK"),
    ModelProfile("llama-3.1-8b-hf", "hf", os.getenv("HF_MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct"),
                 "open", "self_hosted", cost_tier=1, latency_tier=2, quality_tier=2,
                 good_for=("classification","extraction"), license="llama-3.1-community",
                 notes="HF Inference Endpoint or TGI/vLLM on your GPU (docs/07-huggingface-deploy.md)"),
    ModelProfile("qwen2.5-7b-hf", "hf", "Qwen/Qwen2.5-7B-Instruct", "open", "self_hosted",
                 cost_tier=1, latency_tier=2, quality_tier=2, good_for=("classification","extraction","codegen"),
                 license="apache-2.0", notes="permissive license; strong small open model"),
    # --- OpenAI (closed, vendor API). 4th provider / 2nd US vendor in the bake-off. LLM_PROVIDER=openai
    #     or MODEL_PROFILE=gpt-4o-api selects it. quality_tier stays a placeholder until a real eval fills it. ---
    ModelProfile("gpt-4o-api", "openai", os.getenv("OPENAI_MODEL", "gpt-4o"),
                 "closed", "vendor_api", cost_tier=3, latency_tier=2, quality_tier=5,
                 good_for=("reasoning","extraction","summarization","codegen"),
                 notes="OpenAI GPT-4o; needs OPENAI_API_KEY"),
]}

def missing_credential(profile_id: str) -> str | None:
    """Return a one-line skip reason if the profile's provider has no usable credential, else None.
    Lets the bake-off SKIP a model cleanly (exit 0) instead of running it into per-row auth failures."""
    p = REGISTRY[profile_id]
    if p.provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY", "").strip():
        return "no ANTHROPIC_API_KEY"
    if p.provider == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
        return "no OPENAI_API_KEY"
    if p.provider == "bedrock" and not (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")):
        return "no AWS credentials (AWS_ACCESS_KEY_ID / AWS_PROFILE)"
    if p.provider == "hf" and not (os.getenv("HF_ENDPOINT_URL") or os.getenv("HUGGINGFACEHUB_API_TOKEN")):
        return "no HF endpoint / HUGGINGFACEHUB_API_TOKEN"
    return None


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

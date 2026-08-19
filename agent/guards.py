"""Guards = layered safety rails. Each maps to a MANIFEST D-### row and a catch-proven test.

Layer model (docs/04-guardrails.md):
  L0 deterministic, in-process, always on  — regex PII/injection, budgets, allowlist, schema   (ms, free)
  L1 deterministic, library                — Presidio PII (GUARD_PII=presidio)                  (ms, free)
  L2 model-based classifier                — Llama Prompt Guard / Lakera / your HF classifier   (10s of ms)
  L3 provider guardrail                    — Bedrock Guardrails (attached in models.py)          (in-band)
  L4 grounding on OUTPUT                   — citations ⊆ retrieved ids; else confidence capped   (D-012)
  L5 human                                 — HITL interrupt on side-effect tools                 (D-004)
Deterministic where I can, model-judged where I must, humans on the residual.
"""
import os, re, json
from .state import AgentOutput

MAX_STEPS      = int(os.getenv("MAX_STEPS", 12))
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", 8))
MAX_COST_USD   = float(os.getenv("MAX_COST_USD", 0.50))
GUARD_PII      = os.getenv("GUARD_PII", "regex")            # regex | presidio
GUARD_INJ      = os.getenv("GUARD_INJECTION", "regex")      # regex | promptguard | lakera
GROUNDING_MIN  = float(os.getenv("GROUNDING_MIN", 0.0))     # fraction of citations that must resolve (1.0 = all)

_PII = [(re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
        (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[CARD]"),
        (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
        (re.compile(r"\b(?:\+?1[ -.]?)?\(?\d{3}\)?[ -.]?\d{3}[ -.]?\d{4}\b"), "[PHONE]")]
_INJECTION = re.compile(r"(ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)?\s*instructions|you are now|"
                        r"system prompt|developer mode|disregard\s+(all|your|the)|reveal\s+(your|the)\s+(prompt|instructions)|"
                        r"\bDAN\b|jailbreak)", re.I)

class GuardError(Exception): ...

# ---------- L0/L1 PII ----------
def redact_pii(text: str) -> str:
    if GUARD_PII == "presidio":
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            res = AnalyzerEngine().analyze(text=text, language="en")
            return AnonymizerEngine().anonymize(text=text, analyzer_results=res).text
        except ImportError:
            pass  # fall through to regex; never fail open silently — regex still runs
    for rx, tag in _PII: text = rx.sub(tag, text)
    return text

# ---------- L0/L2 injection ----------
def injection_score(text: str) -> float:
    """0..1 probability of injection. Regex is a hard 1.0 on match; classifiers add a soft score."""
    if _INJECTION.search(text): return 1.0
    if GUARD_INJ == "promptguard":
        try:
            from transformers import pipeline
            clf = pipeline("text-classification", model=os.getenv("PROMPTGUARD_MODEL", "meta-llama/Prompt-Guard-86M"))
            r = clf(text[:2000])[0]
            return float(r["score"]) if r["label"].upper() in {"INJECTION", "JAILBREAK"} else 0.0
        except Exception: return 0.0
    if GUARD_INJ == "lakera":
        try:
            import requests
            r = requests.post("https://api.lakera.ai/v2/guard", json={"messages": [{"role": "user", "content": text}]},
                              headers={"Authorization": f"Bearer {os.environ['LAKERA_API_KEY']}"}, timeout=3).json()
            return 1.0 if r.get("flagged") else 0.0
        except Exception: return 0.0
    return 0.0

def input_guard(text: str) -> str:                       # D-005
    if injection_score(text) >= float(os.getenv("INJECTION_THRESHOLD", 0.5)):
        raise GuardError("prompt-injection pattern detected")
    return redact_pii(text)

# ---------- budgets ----------
def budget_guard(step_count: int, tool_calls: int, cost_usd: float = 0.0):   # D-001, D-007
    if step_count > MAX_STEPS: raise GuardError(f"max_steps {MAX_STEPS} exceeded")
    if tool_calls > MAX_TOOL_CALLS: raise GuardError(f"max_tool_calls {MAX_TOOL_CALLS} exceeded")
    if cost_usd > MAX_COST_USD: raise GuardError(f"cost budget ${MAX_COST_USD} exceeded")

# ---------- L4 output + grounding ----------
def output_guard(raw: dict, retrieved_ids: set[str] | None = None) -> AgentOutput:   # D-002, D-003, D-012
    out = AgentOutput.model_validate(raw)
    out.answer = redact_pii(out.answer)                  # never leak PII on the way out
    if retrieved_ids is not None and out.citations:
        ok = [c for c in out.citations if c in retrieved_ids]
        frac = len(ok) / len(out.citations)
        if frac < GROUNDING_MIN:
            raise GuardError(f"ungrounded citations: {set(out.citations) - set(ok)}")
        if frac < 1.0:                                   # partial grounding → cap confidence, keep only valid cites
            out.citations = ok; out.confidence = min(out.confidence, 0.5)
    elif retrieved_ids is not None and not out.citations and out.confidence > 0.7:
        out.confidence = 0.7                             # confident claims with no evidence are not allowed
    return out

def extract_retrieved_ids(messages) -> set[str]:
    """Collect chunk ids from ToolMessages produced by search_kb — the only legal citation space."""
    ids = set()
    for m in messages:
        if getattr(m, "type", "") == "tool" or m.__class__.__name__ == "ToolMessage":
            try:
                for h in json.loads(m.content):
                    if isinstance(h, dict) and "id" in h: ids.add(h["id"])
            except Exception: pass
    return ids

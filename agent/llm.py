"""D-008: one function, provider-agnostic. Selection logic lives in agent/models.py (D-009)."""
import os
from .models import select_model, REGISTRY

def get_llm(temperature: float = 0.0, task_class: str = "reasoning"):
    # Back-compat: LLM_PROVIDER still works (maps to the first profile of that provider).
    p = os.getenv("LLM_PROVIDER")
    if p and not os.getenv("MODEL_PROFILE"):
        prof = next(x for x in REGISTRY.values() if x.provider == p)
    else:
        prof = select_model(task_class=task_class)  # honours MODEL_PROFILE / DATA_RESIDENCY env
    return prof.build(temperature=temperature)

"""D-009 model selection is deterministic and constraint-driven."""
import os, pytest
from agent.models import select_model, REGISTRY

def test_residency_constraint(monkeypatch):
    monkeypatch.delenv("MODEL_PROFILE", raising=False)
    p = select_model("reasoning", residency="customer_vpc")
    assert p.provider == "bedrock" and p.model.startswith("us.")      # inference-profile id, not bare model id

def test_open_weights_preference(monkeypatch):
    monkeypatch.delenv("MODEL_PROFILE", raising=False)
    p = select_model("classification", prefer_open=True)
    assert p.weights == "open"

def test_cost_ceiling(monkeypatch):
    monkeypatch.delenv("MODEL_PROFILE", raising=False)
    p = select_model("classification", max_cost_tier=1)
    assert p.cost_tier == 1

def test_no_match_is_loud(monkeypatch):
    monkeypatch.delenv("MODEL_PROFILE", raising=False)
    with pytest.raises(LookupError): select_model("codegen", residency="self_hosted", min_quality_tier=5)

def test_env_override(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "claude-haiku-api")
    assert select_model("reasoning").id == "claude-haiku-api"

def test_every_profile_has_good_for_and_license():
    for p in REGISTRY.values():
        assert p.good_for and p.license

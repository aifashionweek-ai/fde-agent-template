"""The /hub 'Governance in 6 scenarios' panel: all six scenarios render with their verdict + the
one-line 'what it proves' story, and every verdict is READ from the real scenario-run evidence
(evals/fixtures/scenario_verdicts.json produced by scripts/scenario_check.py), never hand-typed (J-02).
"""
import json
import pathlib

from fastapi.testclient import TestClient

from api.main import app

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERDICTS = ROOT / "evals" / "fixtures" / "scenario_verdicts.json"
SCENARIOS = ["policy_read", "self_reset", "cross_user", "mutate", "injection", "a2a"]
STORY_MARKERS = ["human disposes", "authz layer", "proposal hash", "data, not instructions", "no approval authority"]

client = TestClient(app)


def test_verdicts_json_is_real_run_evidence():
    assert VERDICTS.exists(), "scenario_verdicts.json missing — run bash scripts/run_all.sh --scenarios"
    data = json.loads(VERDICTS.read_text())
    assert set(SCENARIOS) <= set(data["scenarios"]), "all 6 scenarios must be present"
    assert "generated" in data                       # provenance timestamp of the real run


def test_hub_panel_renders_all_six_with_real_verdicts():
    """Served /hub shows the 6-scenario panel; each verdict shown == the verdict in the real-run JSON."""
    html = client.get("/hub").text
    assert "Governance in 6 scenarios" in html
    data = json.loads(VERDICTS.read_text())["scenarios"]
    for key in SCENARIOS:
        verdict = data[key]["verdict"]
        # the exact measured verdict appears in the panel (traceable to the JSON, not invented)
        assert verdict in html, f"{key} verdict {verdict!r} not rendered"
    # the interview narration is on-screen
    for marker in STORY_MARKERS:
        assert marker in html, f"missing story line: {marker}"
    # self-contained: the panel adds no external asset link
    assert "<link" not in html and 'src="http' not in html


def test_panel_verdicts_are_not_hardcoded_in_generator():
    """Catch-proof: the generator reads the verdict from JSON — it does not hardcode ANSWERED/GATED/etc.
    per scenario. Re-render with a mutated verdict and the panel must reflect it."""
    from scripts import build_scenarios
    mutated = {"generated": "test", "all_green": False,
               "scenarios": {k: {"verdict": "ZZZ", "expected": "?", "ok": False} for k in SCENARIOS}}
    panel = build_scenarios.render(mutated)
    assert panel.count("ZZZ") == 6, "generator must render the verdict FROM the data, not a hardcoded one"

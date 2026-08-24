"""The /evals stop is rendered from the REAL extracted JSON (presentation/data/evals_*.json +
discrepancies.json) — never hardcoded. Guards: route 200, real values surface, self-contained, and a
catch-proof that a JSON change surfaces on the page."""
import json
import pathlib

from fastapi.testclient import TestClient

from api.main import app
from scripts.build_evals import render

client = TestClient(app)
DATA = pathlib.Path(__file__).resolve().parent.parent / "presentation" / "data"


def _load():
    return (json.loads((DATA / "evals_h2a.json").read_text()),
            json.loads((DATA / "evals_a2a.json").read_text()),
            json.loads((DATA / "discrepancies.json").read_text()))


def test_evals_route_200():
    r = client.get("/evals")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "how i know it works" in r.text.lower()


def test_render_is_self_contained():
    html = render(*_load())
    assert html.lstrip().startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html
    assert "Space Grotesk" in html and "JetBrains Mono" in html


def test_values_come_from_json_not_hardcoded():
    h2a, a2a, disc = _load()
    html = render(h2a, a2a, disc)
    # H2A totals from the JSON counts (53 cases, 0 breaches)
    assert str(h2a["counts"]["total"]) in html
    assert str(h2a["last_run_result"]["invariant_breaches"]) in html
    # a real discrepancy id + its how_found signal, and D-045 telemetry headline
    d045 = next(d for d in disc["discrepancies"] if d["id"] == "D-045")
    assert "D-045" in html and "telemetry" in html.lower()
    assert d045["test_that_locks_it"] in html
    # an a2a channel term surfaces
    assert any(s["channel"] in html for s in a2a["scenarios"])


def test_d045_is_the_headline_first_discrepancy():
    html = render(*_load())
    ids = [i for i in ("D-045", "D-034", "D-037", "D-038", "D-041", "D-042", "D-043") if f"{i} ·" in html]
    assert ids and ids[0] == "D-045"           # telemetry-caught defect ordered first


def test_render_tracks_json_changes():
    """Catch-proof: a marker discrepancy injected into the JSON surfaces on the page."""
    h2a, a2a, disc = _load()
    disc = {**disc, "discrepancies": disc["discrepancies"] + [
        {"id": "D-ZZZ", "title": "ZZ-Marker-Defect", "how_found": "red-first (marker)",
         "what_was_wrong": "x", "fix": "y", "interaction_type": "both", "test_that_locks_it": "tests/marker.py"}]}
    assert "ZZ-Marker-Defect" in render(h2a, a2a, disc)

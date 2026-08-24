"""The /deploy stop maps a 3-day roadmap to REAL gaps read from presentation/data/*.json — never invented.
Consistency pin: the Cyrillic xfail count on /deploy MUST equal the one /evals renders (same JSON source)."""
import json
import pathlib

from fastapi.testclient import TestClient

from api.main import app
from scripts.build_deploy import render

client = TestClient(app)
DATA = pathlib.Path(__file__).resolve().parent.parent / "presentation" / "data"


def _load():
    j = {n: json.loads((DATA / f"{n}.json").read_text()) for n in
         ["infra", "logs", "evals_h2a", "evals_a2a", "discrepancies"]}
    return j["infra"], j["logs"], j["evals_h2a"], j["evals_a2a"], j["discrepancies"]


def test_deploy_route_200():
    r = client.get("/deploy")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "3 days" in r.text.lower()


def test_render_is_self_contained():
    html = render(*_load())
    assert html.lstrip().startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html
    assert "Space Grotesk" in html and "JetBrains Mono" in html


def test_roadmap_maps_to_real_gaps():
    html = render(*_load())
    # real thin-items from the JSONs, not invented capabilities
    assert "BM25" in html and "Pinecone" in html                 # retrieval gap (infra stub)
    infra = _load()[0]
    logs = _load()[1]
    assert logs["honest_summary"][:40] in html                   # the durable-audit-log gap, verbatim
    assert "IdP" in html                                          # no real IdP gap
    # the 3-day structure is present
    assert "Day 1" in html and "Day 2" in html and "Day 3" in html


def test_xfail_count_matches_evals():
    """Consistency pin: /deploy renders the SAME xfail count /evals reads from the same JSON."""
    infra, logs, h2a, a2a, disc = _load()
    xfail = h2a["counts"]["xfail"]
    html = render(infra, logs, h2a, a2a, disc)
    assert f"{xfail} documented xfail residuals" in html         # read from JSON, not hardcoded


def test_render_tracks_json_changes():
    """Catch-proof: bumping the xfail count in the JSON changes the rendered page."""
    infra, logs, h2a, a2a, disc = _load()
    h2a2 = {**h2a, "counts": {**h2a["counts"], "xfail": 999}}
    assert "999 documented xfail residuals" in render(infra, logs, h2a2, a2a, disc)

"""The /signal stop turns REAL measured data into engineering recommendations — NO trained-model artifacts
(no loss/accuracy/ROC). Guards: route 200, real telemetry + eval numbers surface, recall is a single-k stat
(NOT a fabricated curve), the only SVGs are the real telemetry bars, self-contained, catch-proof."""
import json
import pathlib

from fastapi.testclient import TestClient

from api.main import app
from scripts.build_signal import render

client = TestClient(app)
DATA = pathlib.Path(__file__).resolve().parent.parent / "presentation" / "data"
FIX = pathlib.Path(__file__).resolve().parent.parent / "evals" / "fixtures"


def _load():
    return (json.loads((DATA / "evals_h2a.json").read_text()),
            json.loads((FIX / "telemetry_runs.json").read_text()),
            json.loads((FIX / "mcp_vs_graph.json").read_text()))


def test_signal_route_200():
    r = client.get("/signal")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "recommend" in r.text.lower()


def test_render_is_self_contained():
    html = render(*_load(), 1.0, 0.0)
    assert html.lstrip().startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html
    assert "Space Grotesk" in html and "JetBrains Mono" in html


def test_numbers_trace_to_real_json():
    h2a, runs, mcp = _load()
    html = render(h2a, runs, mcp, 1.0, 0.0)
    # a real telemetry value (injection run token total) appears
    inj = runs["injection"]["trace"]["totals"]["tokens"]
    assert f"{inj:,}" in html
    # the real MCP-vs-graph numbers appear
    assert str(mcp["mcp"]["tokens"]) in html and f'{mcp["graph"]["tokens"]:,}' in html
    # a real eval score (recall/groundedness == 1.0) appears
    assert "1.0" in html


def test_recall_is_single_k_stat_not_a_curve():
    """Phase-1 honesty: the scorer measures a SINGLE k, so recall is a labeled stat — no fabricated curve,
    and no training-metric chart language."""
    html = render(*_load(), 1.0, 0.0).lower()
    assert "single k" in html                              # labeled as one measured k
    assert "recall@k curve" not in html and "training curve" not in html
    # loss/accuracy/roc appear ONLY in the 'there are no such curves' disclaimer, never as a chart title
    assert "no loss/accuracy/roc curves here" in html


def test_only_real_telemetry_svgs():
    """The inline SVGs are the real per-run telemetry bars (tokens/latency/cost) — 3, no more."""
    html = render(*_load(), 1.0, 0.0)
    assert html.count("<svg ") == 3


def test_render_tracks_json_changes():
    """Catch-proof: bumping a telemetry token total changes the rendered page."""
    h2a, runs, mcp = _load()
    runs2 = json.loads(json.dumps(runs))
    runs2["injection"]["trace"]["totals"]["tokens"] = 424242
    assert "424,242" in render(h2a, runs2, mcp, 1.0, 0.0)

"""The /a2a stop is rendered from the REAL extracted JSON (evals_a2a.json + a2a_prompt.json) — never
hardcoded. Guards: route 200, real scenario values + the MCP-boundary D-025 reference surface,
self-contained, and a catch-proof that a JSON change surfaces."""
import json
import pathlib

from fastapi.testclient import TestClient

from api.main import app
from scripts.build_a2a import render

client = TestClient(app)
DATA = pathlib.Path(__file__).resolve().parent.parent / "presentation" / "data"


def _load():
    return (json.loads((DATA / "evals_a2a.json").read_text()),
            json.loads((DATA / "a2a_prompt.json").read_text()))


def test_a2a_route_200():
    r = client.get("/a2a")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "governance composes" in r.text.lower()


def test_render_is_self_contained():
    html = render(*_load())
    assert html.lstrip().startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html
    assert "Space Grotesk" in html and "JetBrains Mono" in html


def test_values_come_from_json_not_hardcoded():
    a2a, prompt = _load()
    html = render(a2a, prompt)
    # real scenario ids + a channel term
    assert all(s["id"] in html for s in a2a["scenarios"])          # every scenario surfaces
    assert "console_channel" in html                               # a real channel
    assert "policy_channel" in html or "allow_tools" in html       # the policy-deny case
    # the settled prompt, verbatim from the JSON (HTML-escaped)
    import html as _h
    assert _h.escape(prompt["settled_prompt"]) in html


def test_mcp_boundary_is_stated():
    html = render(*_load())
    assert "D-025" in html and "mcp_server.py" in html             # the deliberate MCP decision + file
    assert "not exposed over mcp" in html.lower() or "not exposed over MCP".lower() in html.lower()


def test_render_tracks_json_changes():
    """Catch-proof: a marker scenario injected into the JSON surfaces on the page."""
    a2a, prompt = _load()
    a2a2 = {**a2a, "scenarios": a2a["scenarios"] + [
        {"id": "a2a-ZZZ", "input": "marker", "what_propagates": "x", "expected_gate_behavior": "y",
         "channel": "marker_channel", "last_run": "pass"}]}
    assert "a2a-ZZZ" in render(a2a2, prompt)

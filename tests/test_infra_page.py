"""The /infra stop is rendered from the REAL extracted JSON (presentation/data/*.json) — never hardcoded.
Guards: the generator surfaces known real values, the page is self-contained (shared invariant), and the
route serves 200. Catch-proof: change a value in the JSON and the rendered page changes with it."""
import json
import pathlib

from fastapi.testclient import TestClient

from api.main import app
from scripts.build_infra import render

client = TestClient(app)
DATA = pathlib.Path(__file__).resolve().parent.parent / "presentation" / "data"


def _load():
    return (json.loads((DATA / "infra.json").read_text()),
            json.loads((DATA / "tools.json").read_text()),
            json.loads((DATA / "logs.json").read_text()))


def test_infra_route_200():
    r = client.get("/infra")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "where is what" in r.text.lower()


def test_render_is_self_contained():
    html = render(*_load())
    assert html.lstrip().startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html      # shared self-contained invariant
    assert "Space Grotesk" in html and "JetBrains Mono" in html


def test_values_come_from_the_json_not_hardcoded():
    infra, tools, logs = _load()
    html = render(infra, tools, logs)
    # a real infra component + its status tag
    bedrock = next(c for c in infra["components"] if "Bedrock" in c["name"])
    assert bedrock["name"] in html and f'tag {bedrock["status"]}' in html
    # a real tool name + kind + its MCP exposure
    reset = next(t for t in tools["tools"] if t["name"] == "reset_access")
    assert "reset_access" in html and f'tag {reset["kind"]}' in html   # privileged
    assert "withheld" in html                                          # action tools not on MCP
    # a real log stream + the honest absent-capability summary
    assert logs["honest_summary"][:40] in html
    # all four status tags legend present
    for tag in ("present", "documented", "stub", "absent"):
        assert f'tag {tag}' in html


def test_render_tracks_json_changes():
    """Catch-proof: injecting a made-up component surfaces on the page — proves it reads the JSON."""
    infra, tools, logs = _load()
    infra = {"components": infra["components"] + [
        {"name": "ZZ-Marker-Component", "role": "test", "where_configured": "x:1", "status": "absent", "note": "n"}]}
    assert "ZZ-Marker-Component" in render(infra, tools, logs)

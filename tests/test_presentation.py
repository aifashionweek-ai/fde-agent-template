"""Presentation surfaces are served read-only (docs/PRESENTATION.md). NOT a control D-row — these are
demo/presentation static files, no logic. Guards only that /hub and /business return the committed HTML.
(/problem and /audit serve generated, gitignored reports, so they are not asserted here.)"""
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_hub_served():
    r = client.get("/hub")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "demo hub" in r.text and "/dashboard" in r.text     # links wired to served routes


def test_business_served():
    r = client.get("/business")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "scoping brief" in r.text


def test_missing_presentation_file_is_404_not_500():
    """A route whose backing file is absent returns a clean 404, never a 500."""
    # /audit serves a generated (possibly-absent) report; it must 404 gracefully, not crash.
    r = client.get("/audit")
    assert r.status_code in (200, 404)

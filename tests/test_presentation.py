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
    # the three-act brief (not the old placeholder). Deeper token/section assertions live in
    # tests/test_presentation_tokens.py.
    assert "scoping brief" in r.text.lower()
    assert "The agent this becomes" in r.text


def test_all_six_stops_return_200():
    """Every demo stop returns 200 — a missing generated report degrades to a placeholder, never a 404."""
    for p in ["/", "/hub", "/business", "/dashboard", "/problem", "/audit"]:
        assert client.get(p).status_code == 200, p


def test_missing_backing_file_serves_placeholder_not_404():
    """A route whose backing file is absent returns a clean 200 'run X' page, never a raw 404/500."""
    import pathlib
    from api.main import _serve_html
    resp = _serve_html(pathlib.Path("/no/such/report.html"), hint="make audit")
    assert resp.status_code == 200
    body = bytes(resp.body).decode()
    assert "hasn't been generated" in body and "make audit" in body

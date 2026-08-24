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
    """A route whose backing file is absent returns a clean 200 'run X' page, never a raw 404/500 —
    AND the placeholder itself carries the shared house-style tokens, so the drift test stays hermetic
    on a cold clone / CI where generated reports don't exist yet (catch-proof for that fix)."""
    import pathlib
    from api.main import _serve_html
    resp = _serve_html(pathlib.Path("/no/such/report.html"), hint="make audit")
    assert resp.status_code == 200
    body = bytes(resp.body).decode()
    assert "hasn't been generated" in body and "make audit" in body
    assert "Space Grotesk" in body and "JetBrains Mono" in body and "--line" in body   # on-brand, hermetic


def test_runnable_served():
    """STOP 12 'Run it yourself' shows the REAL verified quickstart + the graceful no-key message."""
    r = client.get("/runnable")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    # the verified quickstart commands appear verbatim
    for cmd in ["python3.11 -m venv .venv", "pip install -r requirements.txt", "make demo", "make check"]:
        assert cmd in r.text, f"missing quickstart command: {cmd}"
    # the graceful no-credential message text appears (the reviewer-trust point)
    assert "No model credentials found" in r.text
    assert "export ANTHROPIC_API_KEY=" in r.text
    # the measured, verified result is shown (robust to unrelated test-count drift: assert the shape,
    # not a brittle total — the page states the real number, this just proves a real result is present)
    assert "2 skipped" in r.text and "passed" in r.text
    # self-contained: no external stylesheet / font / script / @import (URLs in code text are fine)
    assert "<link" not in r.text and "@import" not in r.text
    assert 'src="http' not in r.text and 'stylesheet' not in r.text

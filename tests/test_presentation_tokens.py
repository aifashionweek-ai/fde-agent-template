"""Catch-proof: every served presentation surface carries the shared house-style type system.

The reference design system is the three-act business brief (Space Grotesk + JetBrains Mono on an
ink-blue/cool-white palette). This suite fetches EVERY served route and asserts the shared font
stack + a shared palette var are present, so a page that drifts off the design system turns red
(J-02 — the verdict is computed from the real served bytes, not asserted). It also proves the check
actually bites: a synthetic page missing the fonts must fail the same predicate.

Source of truth for the invariant: presentation/tokens.py.
"""
from fastapi.testclient import TestClient

from api.main import app
from presentation.tokens import (
    FONT_MONO_NAME,
    FONT_SANS_NAME,
    SERVED_PAGES,
    SHARED_PALETTE_VAR,
)

client = TestClient(app)


def _carries_house_style(html: str) -> bool:
    """The house-style invariant, computed from the page's own bytes."""
    return (
        FONT_SANS_NAME in html
        and FONT_MONO_NAME in html
        and SHARED_PALETTE_VAR in html
    )


def test_every_served_page_carries_shared_type_system():
    """All 12 served surfaces load the shared font stack + palette var — no page drifts off-system."""
    missing = {}
    for route in SERVED_PAGES:
        r = client.get(route)
        assert r.status_code == 200, f"{route} -> {r.status_code}"
        assert "text/html" in r.headers["content-type"], route
        gaps = [tok for tok in (FONT_SANS_NAME, FONT_MONO_NAME, SHARED_PALETTE_VAR) if tok not in r.text]
        if gaps:
            missing[route] = gaps
    assert not missing, f"pages missing shared house-style tokens: {missing}"


def test_business_is_three_act_not_placeholder():
    """/business serves the three-act brief, and the OLD placeholder can never silently return."""
    html = client.get("/business").text
    # three-act sections render (headers are static; matrix/glossary are JS-hydrated containers)
    for section in ["The agent this becomes", "What we found", "How we prioritize", "glossary"]:
        assert section.lower() in html.lower(), f"missing three-act section: {section}"
    # the stale scaffold must be gone (catch-proof against regressing to the old file)
    for stale in ["PLACEHOLDER scaffold", "Where AI fits — and where it must not", "Build-first (impact"]:
        assert stale not in html, f"old placeholder resurfaced: {stale}"


def test_invariant_actually_bites():
    """Catch-proof: a page stripped of the shared fonts must FAIL the predicate — the guard isn't decoration."""
    good = f"<style>--sans:'{FONT_SANS_NAME}';--mono:'{FONT_MONO_NAME}';{SHARED_PALETTE_VAR}:#eee;</style>"
    assert _carries_house_style(good)
    assert not _carries_house_style(good.replace(FONT_SANS_NAME, "Comic Sans"))
    assert not _carries_house_style(good.replace(FONT_MONO_NAME, "Courier"))
    assert not _carries_house_style(good.replace(SHARED_PALETTE_VAR, "--nope"))

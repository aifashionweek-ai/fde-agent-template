"""The 13-stop showcase: generators read real data (J-01), never fabricate; a stop with no data renders a
house-style 'pending' card, never a fake or a 404 (J-02); every served page carries the shared design
tokens (single-sourced in presentation/tokens.py), so nothing drifts. Catch-proof included.
"""
import importlib

from fastapi.testclient import TestClient

from api.main import app
from presentation.build_all import run
from presentation.tokens import (
    FONT_MONO_NAME,
    FONT_SANS_NAME,
    SERVED_PAGES,
    SHARED_PALETTE_VAR,
    STOPS,
)

client = TestClient(app)

GENERATED = [s for s in STOPS if s.get("out")]


def _house_style(html: str) -> bool:
    return FONT_SANS_NAME in html and FONT_MONO_NAME in html and SHARED_PALETTE_VAR in html


def _self_contained(html: str) -> bool:
    return ("<link" not in html and "@import" not in html
            and 'src="http' not in html and "stylesheet" not in html)


def test_every_generator_emits_house_style_selfcontained():
    """Each generator returns (status, html); the html is on-brand and self-contained regardless of status."""
    for s in GENERATED:
        mod = importlib.import_module(f"presentation.build_{s['key']}")
        status, html = mod.build()
        assert status in {"filled", "placeholder", "error"}, s["key"]
        assert _house_style(html), f"{s['key']} dropped the shared tokens"
        assert _self_contained(html), f"{s['key']} has an external asset link"


def test_missing_data_renders_pending_not_fake():
    """A stop whose data file is absent renders the 'pending' card (honest), not fabricated content."""
    import presentation.build_business as b
    status, html = b.build()          # skeleton has no business.json
    assert status == "placeholder"
    assert "Pending" in html and "business.json" in html


# stops that are legitimately always-filled: they carry NO run-derived number, so there is nothing to fake.
#   runnable — the fixed quickstart contract (instructions, verifiable by running them, not data).
_NO_DATA_CLAIM = {"runnable"}


def test_no_generator_fabricates_absent_artifact_is_placeholder(tmp_path):
    """ANTI-HARDCODING catch-proof (J-02, the whole point): every data-driven stop, built against an EMPTY
    root (no data files at all), MUST return 'placeholder'. A generator that hardcoded a number instead of
    reading its artifact would render 'filled' here — this test would then fail and NAME it. This is
    generic: it covers every current and future stop automatically. Paired with
    test_evals_and_audit_fill_from_committed_report (which proves 'filled' happens when the artifact IS
    present), it proves each generator genuinely branches on the real file — never a constant."""
    import importlib
    offenders = {}
    for s in GENERATED:
        if s["key"] in _NO_DATA_CLAIM:
            continue
        mod = importlib.import_module(f"presentation.build_{s['key']}")
        status, _ = mod.build(tmp_path)          # tmp_path has none of the data files
        if status != "placeholder":
            offenders[s["key"]] = status
    assert not offenders, f"stops that did NOT degrade to placeholder on an empty root (hardcoded data?): {offenders}"


def test_evals_and_audit_fill_from_committed_report():
    """On a bare clone the eval-backed stops fill from the committed sample report (proves 'filled' works)."""
    import presentation.build_audit as au
    import presentation.build_evals as ev
    assert ev.build()[0] == "filled"
    assert au.build()[0] == "filled"


def test_orchestrator_matrix_no_errors():
    """`make showcase` completes with zero generator errors and a mix of filled + placeholder."""
    results = run()
    statuses = [st for *_, st in results]
    assert "error" not in statuses, f"a generator errored: {results}"
    assert statuses.count("filled") >= 4        # hub, evals, audit, runnable at minimum
    assert statuses.count("placeholder") >= 1    # the domain-data stops on the skeleton


def test_served_pages_carry_tokens_even_as_placeholder():
    """Every served route is 200 and on-brand — including the cold-clone placeholder fallback (hermetic)."""
    for route in SERVED_PAGES:
        r = client.get(route)
        assert r.status_code == 200, f"{route} -> {r.status_code}"
        assert _house_style(r.text), f"{route} served without house-style tokens"


def test_invariant_actually_bites():
    """Catch-proof: a page stripped of the shared fonts/palette must FAIL the predicate — not decoration."""
    good = f"<style>--x:1;{SHARED_PALETTE_VAR}:#000</style>{FONT_SANS_NAME} {FONT_MONO_NAME}"
    assert _house_style(good)
    assert not _house_style(good.replace(FONT_SANS_NAME, "Comic Sans"))
    assert not _house_style(good.replace(SHARED_PALETTE_VAR, "--nope"))

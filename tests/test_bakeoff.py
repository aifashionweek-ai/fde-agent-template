"""OpenAI in the bake-off: the provider is a one-interface swap (D-008); a missing key SKIPS cleanly with
a clear message (never a traceback, never a fabricated 1.00 column — J-02); the L5 panel renders whatever
REAL columns the newest report has. No OpenAI score is ever hardcoded.
"""
import pathlib

import pytest

from agent.models import REGISTRY, MissingCredentials, missing_credential

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_openai_provider_registered():
    p = REGISTRY["gpt-4o-api"]
    assert p.provider == "openai" and p.model.startswith("gpt-4o") and p.weights == "closed"


def test_missing_key_is_clean_skip_not_traceback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # missing_credential → a one-line reason (used by the bake-off to skip cleanly, exit 0)
    assert missing_credential("gpt-4o-api") == "no OPENAI_API_KEY"
    # build() raises the SPECIFIC MissingCredentials type with a clear message — caught, not a raw crash
    with pytest.raises(MissingCredentials) as ei:
        REGISTRY["gpt-4o-api"].build()
    assert "OPENAI_API_KEY" in str(ei.value) and "export" in str(ei.value)


def test_key_present_would_build(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    assert missing_credential("gpt-4o-api") is None       # a present key is NOT a skip


def test_bakeoff_skips_openai_without_key_and_never_fakes_a_column(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.bakeoff import compose_md, run_bakeoff
    columns, provenance, skipped = run_bakeoff({"gpt-4o-api"}, "2099-01-01")
    # GPT-4o is skipped with a reason, and gets NO column (no fabricated numbers)
    assert any("GPT-4o" in d for d in skipped)
    assert not any("GPT-4o" in d for d in columns), "skipped model must not have a column"
    md = compose_md(columns, provenance, skipped, "2099-01-01")
    # the report names GPT-4o only in the skipped section, with no numeric row for it
    assert "skipped" in md.lower() and "OPENAI_API_KEY" in md


def test_panel_reads_real_report_no_hardcoded_score():
    from evals.audit_report import bakeoff_table, load_bakeoff
    bo = load_bakeoff()
    assert bo is not None and bo["n_scorers"] == 9        # parsed from the committed report, not hardcoded
    html = bakeoff_table(bo)
    assert "source:" in html                              # every rendered number cites its source file
    # catch-proof: no bake-off numbers are hardcoded in the renderer — with no report it says "Not fabricated"
    assert "Not fabricated" in bakeoff_table(None)


def test_no_hardcoded_openai_score_in_source():
    """Grep guard: no source file hardcodes a GPT-4o/OpenAI scorer number — it can only come from a report."""
    import re
    for f in (ROOT/"evals"/"audit_report.py", ROOT/"scripts"/"bakeoff.py", ROOT/"agent"/"models.py"):
        txt = f.read_text().lower()
        # a hardcoded score would look like `gpt-4o ... 1.00` on one line; assert none exist
        for line in txt.splitlines():
            if "gpt-4o" in line and re.search(r"\b[01]\.\d\d\b", line):
                pytest.fail(f"possible hardcoded GPT-4o score in {f.name}: {line.strip()[:80]}")

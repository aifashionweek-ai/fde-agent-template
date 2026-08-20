"""D-026 guard: the problem-breakdown report renders all required sections and ranks surfaces correctly.
Catch-proof: drop a section or break the impact/effort sort and a test fails."""
import html
from evals.problem_report import render, _ranked, DEFAULT_PROBLEM

REQUIRED_SECTIONS = [
    "Surface vs. real problem",
    "Surfaces ranked by impact",
    "Where AI fits",
    "must NOT",
    "Success criteria",
    "Build first",
]


def test_all_sections_present():
    out = render(DEFAULT_PROBLEM)
    for s in REQUIRED_SECTIONS:
        assert s in out, f"missing section: {s}"


def test_ranking_is_descending_by_impact_over_effort():
    ranked = _ranked(DEFAULT_PROBLEM["surfaces"])
    ratios = [r["ratio"] for r in ranked]
    assert ratios == sorted(ratios, reverse=True)
    # ratio must actually be impact/effort, not a stored value
    for r in ranked:
        assert abs(r["ratio"] - r["impact"] / r["effort"]) < 1e-9


def test_build_first_is_top_ranked_surface():
    ranked = _ranked(DEFAULT_PROBLEM["surfaces"])
    out = render(DEFAULT_PROBLEM)
    # the top surface is tagged "build first" in the table AND named in the Build-first card
    # (names are HTML-escaped on the way out, e.g. "Q&A" -> "Q&amp;A")
    assert html.escape(ranked[0]["name"]) in out
    assert "build first" in out


def test_self_contained_html():
    out = render(DEFAULT_PROBLEM)
    assert out.lstrip().startswith("<!doctype html>")
    # no external asset references (CSP-safe / offline artifact)
    assert "http://" not in out and "https://" not in out
    assert "<script" not in out

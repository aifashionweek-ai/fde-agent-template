"""D-046 guard: the eval runner's INVARIANT gate is a real gate — it runs the deterministic breach
scorers over every dataset and must report ZERO breaches, and the quality scorers must clear their
thresholds. This is what CI executes (the runner is offline/deterministic). Catch-proof: introduce a
control regression and a breach appears here; flip an expected outcome and the gate goes red."""
from evals.runner import run
from evals.scorers.invariant import SCORERS as INVARIANT
from evals.scorers.quality import SCORERS as QUALITY, THRESHOLDS


def test_no_invariant_breaches():
    rep = run()
    breaches = {l: v["breach_rows"] for l, v in rep["invariant"].items() if v["breaches"]}
    assert breaches == {}, f"invariant breaches: {breaches}"


def test_quality_clears_thresholds():
    rep = run()
    for layer, v in rep["quality"].items():
        assert v["passed"], f"{layer} mean={v['mean']} < threshold={v['threshold']}"


def test_gate_passes_overall():
    assert run()["gate"]["passed"] is True


def test_every_invariant_layer_has_a_dataset_and_rows():
    rep = run()
    for layer in INVARIANT:
        assert rep["invariant"][layer]["total"] + rep["invariant"][layer]["xfail"] > 0, f"{layer} has no rows"


def test_xfail_residuals_are_documented_not_hidden():
    """The known cross-script confusable residual (D-042) is present as xfail — visible, not faked green."""
    rep = run()
    xfail_classes = [x["attack_class"] for v in rep["invariant"].values() for x in v["xfail_rows"]]
    assert "homoglyph_cyrillic" in xfail_classes


def test_scorer_catches_a_forced_regression():
    """Catch-proof: a row asserting an authz DENY that the code ALLOWS must be reported as a breach."""
    from evals.scorers.invariant import score_authz
    bad = {"principal": {"user_id": "alice", "tenant_id": "meridian"}, "action": "reset_access",
           "resource": {"tenant": "meridian", "subject": "alice"}, "expected_control_outcome": "deny"}
    assert score_authz(bad)["passed"] is False           # code allows self-reset; asserting deny -> breach

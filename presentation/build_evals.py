"""Generator · /evals — the eval gate rendered from the REAL report (evals/report/latest.json, else the
committed sample). Shows the invariant breach table, quality thresholds, and the computed gate verdict.
J-02: the verdict is READ from the report, never asserted here. Run: python -m presentation.build_evals
"""
from presentation import _base
from presentation import render as r

KEY = "evals"


def render_filled(data, root, stop):
    gate = data.get("gate", {})
    inv = data.get("invariant", {})
    qual = data.get("quality", {})
    passed = gate.get("passed")

    verdict = r.pill("GATE PASSED", "good") if passed else r.pill("GATE FAILED", "bad")
    breaches = gate.get("invariant_breaches", "?")
    s = r.stats([
        (breaches, "invariant breaches"),
        (sum(v.get("total", 0) for v in inv.values()), "invariant checks"),
        (len(qual), "quality metrics"),
        (sum(v.get("xfail", 0) for v in inv.values()), "documented xfails"),
    ])

    inv_rows = [
        [layer, v.get("total", 0),
         r.pill(str(v.get("breaches", 0)), "bad" if v.get("breaches") else "good"),
         v.get("xfail", 0)]
        for layer, v in inv.items()
    ]
    inv_tbl = r.table(["layer", "checks", "breaches", "xfail"], inv_rows)

    qual_rows = [
        [m, f"{v.get('mean', 0):.2f}", f"{v.get('threshold', 0):.2f}",
         r.pill("pass", "good") if v.get("passed") else r.pill("below", "warn")]
        for m, v in qual.items()
    ]
    qual_tbl = r.table(["metric", "mean", "threshold", "verdict"], qual_rows)

    body = (
        r.section(1, "Verdict", r.card(f"{verdict} &nbsp; {breaches} invariant breach(es). " + s),
                  lead="Computed from the eval report — the gate blocks the deploy if any invariant regresses.")
        + r.section(2, "Invariant breaches by layer", inv_tbl,
                    lead="Deterministic scorers at 1.00 are invariants; any breach is a defect, not a threshold.")
        + r.section(3, "Quality thresholds", qual_tbl,
                    lead="Judged / measured metrics with per-slice thresholds.")
    )
    return r.document(stop["title"], "showcase · stop 07", stop["title"],
                      "The golden set is the spec; this is the computed gate over it.", body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

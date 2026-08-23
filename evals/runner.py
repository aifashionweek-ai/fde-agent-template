"""Eval harness C — one entrypoint (D-046). Runs the INVARIANT set (binary breach scorers; any breach
fails the gate hard) and the QUALITY set (graded 0..1 vs explicit thresholds) across every dataset in
evals/datasets/, and emits one unified report (JSON + human summary) to evals/report/. Egress rows are
xfail-documented (roadmap, not built). Deterministic + offline → runs in CI.

  python -m evals.runner              # run all, write report, exit nonzero on any breach/threshold miss
  python -m evals.runner --quiet      # summary only
  python -m evals.runner --braintrust # also push graded quality scores to Braintrust (needs key)

The invariant scorers reuse the SAME control code the graph uses, so a breach is a real regression.
Judge-based quality (answer relevance, plan efficiency) is Braintrust/nightly — see evals/README.md.
"""
from __future__ import annotations
import json
import pathlib
import sys

from evals.scorers.invariant import SCORERS as INVARIANT
from evals.scorers.quality import SCORERS as QUALITY, THRESHOLDS

ROOT = pathlib.Path(__file__).resolve().parent
DATASETS = ROOT / "datasets"
REPORT = ROOT / "report"


def _load(layer: str) -> list[dict]:
    f = DATASETS / f"{layer}.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()]


def run() -> dict:
    invariant = {}
    for layer, scorer in INVARIANT.items():
        rows = _load(layer)
        # xfail rows are DOCUMENTED residuals (e.g. cross-script confusables, D-042): run + report, never
        # gate on them, never hide them. An xfail that unexpectedly PASSES is surfaced as an xpass.
        gating = [r for r in rows if r.get("status") != "xfail"]
        xfails = [r for r in rows if r.get("status") == "xfail"]
        results = [{**scorer(r), "attack_class": r.get("attack_class")} for r in gating]
        breaches = [r for r in results if not r["passed"]]
        xf = [{"attack_class": r.get("attack_class"), "xpass": scorer(r)["passed"],
               "residual": r.get("residual", "")} for r in xfails]
        invariant[layer] = {"total": len(results), "breaches": len(breaches), "xfail": len(xfails),
                            "breach_rows": [{"attack_class": b["attack_class"], "expected": b["expected"],
                                             "actual": b["actual"], "detail": b["detail"]} for b in breaches],
                            "xfail_rows": xf}

    quality = {}
    for layer, scorer in QUALITY.items():
        rows = _load(layer)
        scores = [scorer(r)["score"] for r in rows]
        mean = round(sum(scores) / len(scores), 3) if scores else 0.0
        thr = THRESHOLDS[layer]
        quality[layer] = {"total": len(scores), "mean": mean, "threshold": thr,
                          "passed": mean >= thr, "scores": scores}

    xfail = _load("egress")
    total_breaches = sum(v["breaches"] for v in invariant.values())
    quality_misses = [l for l, v in quality.items() if not v["passed"]]
    report = {
        "invariant": invariant,
        "quality": quality,
        "xfail": {"egress": {"total": len(xfail), "note": "destination-allowlist / DLP — roadmap, not built"}},
        "gate": {"invariant_breaches": total_breaches, "quality_below_threshold": quality_misses,
                 "passed": total_breaches == 0 and not quality_misses},
    }
    return report


def human_summary(rep: dict) -> str:
    L = ["=" * 64, "EVAL HARNESS C — invariant + quality", "=" * 64, "", "INVARIANT (must-be-zero breaches):"]
    for layer, v in rep["invariant"].items():
        mark = "ok " if v["breaches"] == 0 else "FAIL"
        xf = f"  (+{v['xfail']} xfail residual)" if v.get("xfail") else ""
        L.append(f"  [{mark}] {layer:16} {v['total']-v['breaches']}/{v['total']} pass{xf}"
                 + (f"  BREACHES: {[b['attack_class'] for b in v['breach_rows']]}" if v["breaches"] else ""))
    L.append("")
    L.append("QUALITY (graded vs threshold):")
    for layer, v in rep["quality"].items():
        mark = "ok " if v["passed"] else "FAIL"
        L.append(f"  [{mark}] {layer:16} mean={v['mean']:.2f}  threshold={v['threshold']:.2f}  (n={v['total']})")
    L.append("")
    L.append(f"XFAIL (documented roadmap): egress n={rep['xfail']['egress']['total']} — {rep['xfail']['egress']['note']}")
    g = rep["gate"]
    L.append("")
    L.append(f"GATE: {'PASS' if g['passed'] else 'FAIL'}  "
             f"(invariant breaches={g['invariant_breaches']}, quality misses={g['quality_below_threshold']})")
    L.append("=" * 64)
    return "\n".join(L)


def push_braintrust(rep: dict) -> None:
    try:
        import braintrust
        exp = braintrust.init(project="fde-agent-evalsC")
        for layer, v in rep["quality"].items():
            for i, s in enumerate(v["scores"]):
                exp.log(input=f"{layer}#{i}", scores={layer: s})
        exp.flush()
        print("pushed graded quality to Braintrust")
    except Exception as e:
        print(f"braintrust push skipped: {e}")


def main(argv: list[str]) -> int:
    rep = run()
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "latest.json").write_text(json.dumps(rep, indent=2))
    summary = human_summary(rep)
    (REPORT / "latest.txt").write_text(summary)
    if "--quiet" not in argv:
        print(summary)
    if "--braintrust" in argv:
        push_braintrust(rep)
    return 0 if rep["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

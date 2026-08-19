"""Regression gate: enforce MASTERSCHEMA thresholds against a local results file.
Usage: python -m evals.gate <experiment> [baseline]

Reads evals/results/<experiment>.json (written by evals/harness.py) — no network, no Braintrust
fetch. The gate runs offline in CI; Braintrust is the dashboard, this file is the source of truth.

Exit 1 if: any deterministic scorer < 1.0, any judged scorer below threshold, a slice regresses
> 0.05 vs baseline, calibration ECE > 0.15, judge agreement < 0.80, or fewer rows than the dataset.
"""
import json, os, re, sys, pathlib
from evals.scorers import calibration_error, agreement

ROOT = pathlib.Path(__file__).parent.parent
RESULTS = pathlib.Path(__file__).parent/"results"

THRESH = {}
for line in (ROOT/"MASTERSCHEMA.md").read_text().splitlines():
    m = re.match(r"\|\s*(\w+)\s*\|\s*(deterministic|LLM-judge|meta)\s*\|\s*([<>]=?\s*)?([\d.]+)", line)
    if m: THRESH[m[1]] = (m[2], m[3] or "", float(m[4]))
JUDGE_ALIASES = {"Factuality": "factual"}


def load(experiment: str) -> dict:
    f = RESULTS/f"{experiment}.json"
    if not f.exists():
        raise SystemExit(f"[gate] {f} not found — run `EXPERIMENT={experiment} python -m evals.harness` first")
    return json.loads(f.read_text())


def summarize(payload: dict):
    rows = payload["rows"]
    by_slice, conf_pairs, j1, j2 = {}, [], [], []
    for r in rows:
        sl, sc, out = r["slice"], r.get("scores") or {}, r.get("output") or {}
        by_slice.setdefault(sl, []).append(sc)
        if sc.get("factual") is not None and isinstance(out.get("confidence"), (int, float)):
            conf_pairs.append((float(out["confidence"]), 1.0 if sc["factual"] >= 0.5 else 0.0))
        if sc.get("factual") is not None and sc.get("rubric_pass") is not None:
            j1.append(sc["factual"]); j2.append(sc["rubric_pass"])
    agg = {}
    for sl, lst in by_slice.items():
        keys = set().union(*[s.keys() for s in lst])
        agg[sl] = {k: sum((s.get(k) or 0) for s in lst) / len(lst)
                   for k in keys if any(s.get(k) is not None for s in lst)}
    return agg, calibration_error(conf_pairs), agreement(j1, j2)


def main():
    exp = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else None
    payload = load(exp)
    agg, ece, agr = summarize(payload)
    fails = []

    expected_rows = len([l for l in (ROOT/"evals"/"dataset.jsonl").read_text().splitlines() if l.strip()])
    if payload["n"] < expected_rows:
        fails.append(f"only {payload['n']} rows scored, dataset has {expected_rows}")

    allkeys = set().union(*agg.values()) if agg else set()
    overall = {k: sum(a[k] for a in agg.values() if k in a) / max(1, sum(1 for a in agg.values() if k in a))
               for k in allkeys}
    judged = set(payload.get("judges", []))
    for name, (kind, op, t) in THRESH.items():
        k = JUDGE_ALIASES.get(name, name)
        if kind == "deterministic" and k in overall and overall[k] < 1.0:
            fails.append(f"{k}={overall[k]:.2f} < 1.00")
        if kind == "LLM-judge" and k in overall and k in judged and overall[k] < t:
            fails.append(f"{k}={overall[k]:.2f} < {t}")
    if judged:
        if ece > 0.15: fails.append(f"calibration ECE {ece} > 0.15")
        if agr < 0.80: fails.append(f"judge agreement {agr} < 0.80 (rubric ambiguous — fix the rubric, not the model)")

    if base:
        bagg, _, _ = summarize(load(base))
        for sl in agg:
            for k in agg[sl]:
                if sl in bagg and k in bagg[sl] and agg[sl][k] < bagg[sl][k] - 0.05:
                    fails.append(f"slice {sl}/{k} regressed {bagg[sl][k]:.2f}->{agg[sl][k]:.2f} vs {base}")

    print(f"[gate] {exp}: rows={payload['n']} model={payload.get('model_profile')} "
          f"judges={judged or 'none'} ECE={ece} judge_agreement={agr}")
    for sl, a in sorted(agg.items()):
        print(f"  slice {sl:12s} " + ", ".join(f"{k}={v:.2f}" for k, v in sorted(a.items())))
    if fails:
        print("[gate] FAIL"); [print("   -", f) for f in fails]; sys.exit(1)
    print("[gate] PASS")


if __name__ == "__main__":
    main()

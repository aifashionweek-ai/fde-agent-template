"""Regression gate: compare an experiment to a baseline against MASTERSCHEMA thresholds.
Usage: python -m evals.gate <experiment> [baseline]
Exit 1 if any deterministic scorer < 1.0, any judged scorer below threshold, a slice regresses > 0.05,
calibration ECE > 0.15, or judge agreement < 0.80. This is what makes "the evals passed" mean something.
"""
import os, re, sys, pathlib
from evals.scorers import calibration_error, agreement

THRESH = {}   # parsed from MASTERSCHEMA "## Scorers" table
for line in (pathlib.Path(__file__).parent.parent/"MASTERSCHEMA.md").read_text().splitlines():
    m = re.match(r"\|\s*(\w+)\s*\|\s*(deterministic|LLM-judge|meta)\s*\|\s*([<>]=?\s*)?([\d.]+)", line)
    if m: THRESH[m[1]] = (m[2], m[3] or "", float(m[4]))

def fetch(exp: str):
    from braintrust import init
    import braintrust
    proj = os.getenv("BRAINTRUST_PROJECT", "fde-agent")
    e = braintrust.init(project=proj, experiment=exp, open=True)
    rows = list(e.fetch())
    return rows

def summarize(rows):
    by_slice, conf_pairs, j1, j2 = {}, [], [], []
    for r in rows:
        sl = (r.get("metadata") or {}).get("slice", "untagged"); sc = r.get("scores") or {}
        by_slice.setdefault(sl, []).append(sc)
        out = r.get("output") or {}
        if "Factuality" in sc and isinstance(out, dict) and "confidence" in out:
            conf_pairs.append((float(out["confidence"]), 1.0 if sc["Factuality"] >= 0.5 else 0.0))
        if "Factuality" in sc and "rubric_pass" in sc: j1.append(sc["Factuality"]); j2.append(sc["rubric_pass"])
    agg = {}
    for sl, lst in by_slice.items():
        keys = set().union(*[s.keys() for s in lst])
        agg[sl] = {k: sum(s.get(k, 0) for s in lst) / len(lst) for k in keys}
    return agg, calibration_error(conf_pairs), agreement(j1, j2)

def main():
    exp = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else None
    agg, ece, agr = summarize(fetch(exp)); fails = []
    overall = {k: sum(a[k] for a in agg.values() if k in a) / len(agg) for k in set().union(*agg.values())}
    for k, (kind, op, t) in THRESH.items():
        if k in overall and ((kind == "deterministic" and overall[k] < 1.0) or (kind == "LLM-judge" and overall[k] < t)):
            fails.append(f"{k}={overall[k]:.2f} < {t}")
    if ece > 0.15: fails.append(f"calibration ECE {ece} > 0.15")
    if agr < 0.80: fails.append(f"judge agreement {agr} < 0.80 (rubric ambiguous)")
    if base:
        bagg, _, _ = summarize(fetch(base))
        for sl in agg:
            for k in agg[sl]:
                if sl in bagg and k in bagg[sl] and agg[sl][k] < bagg[sl][k] - 0.05:
                    fails.append(f"slice {sl}/{k} regressed {bagg[sl][k]:.2f}→{agg[sl][k]:.2f}")
    print(f"[gate] {exp}: ECE={ece} agreement={agr}")
    for sl, a in agg.items(): print(f"  slice {sl}: " + ", ".join(f"{k}={v:.2f}" for k, v in sorted(a.items())))
    if fails:
        print("[gate] FAIL"); [print("   -", f) for f in fails]; sys.exit(1)
    print("[gate] PASS")

if __name__ == "__main__": main()

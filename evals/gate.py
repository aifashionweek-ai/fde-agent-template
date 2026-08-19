"""Regression gate: compare an experiment to a baseline against MASTERSCHEMA thresholds.
Usage: python -m evals.gate <experiment-or-prefix> [baseline-or-prefix]

Braintrust auto-suffixes experiment names (baseline -> baseline-b6f3006f); a prefix resolves to the
NEWEST matching experiment. Rows are pulled with the Braintrust SDK's Experiment.fetch(), which returns
one assembled record per dataset row (input/output/expected/scores/metadata) — no span filtering.

Exit 1 if: any deterministic scorer < 1.0, any judged scorer below threshold, a slice regresses > 0.05,
calibration ECE > 0.15, judge agreement < 0.80, OR fewer rows than the dataset (a gate must never pass
on missing data). This is what makes "the evals passed" mean something.
"""
import os, re, sys, pathlib
from evals.scorers import calibration_error, agreement

ROOT = pathlib.Path(__file__).parent.parent
PROJECT = os.getenv("BRAINTRUST_PROJECT", "fde-agent")

THRESH = {}   # parsed from MASTERSCHEMA "## Scorers" table
for line in (ROOT/"MASTERSCHEMA.md").read_text().splitlines():
    m = re.match(r"\|\s*(\w+)\s*\|\s*(deterministic|LLM-judge|meta)\s*\|\s*([<>]=?\s*)?([\d.]+)", line)
    if m: THRESH[m[1]] = (m[2], m[3] or "", float(m[4]))
JUDGE_ALIASES = {"Factuality": "factual"}   # MASTERSCHEMA scorer name -> function name registered in Braintrust


def resolve_name(name: str) -> str:
    """Exact name, or the newest experiment whose name starts with `name`."""
    import requests
    base = os.getenv("BRAINTRUST_API_URL", "https://api.braintrust.dev")
    h = {"Authorization": f"Bearer {os.environ['BRAINTRUST_API_KEY']}"}
    r = requests.get(f"{base}/v1/experiment", params={"project_name": PROJECT, "limit": 200},
                     headers=h, timeout=30).json()
    exps = [e for e in r.get("objects", []) if e["name"] == name or e["name"].startswith(name)]
    if not exps:
        raise SystemExit(f"[gate] no experiment matching '{name}' in project {PROJECT}")
    exps.sort(key=lambda e: e.get("created", ""), reverse=True)
    return exps[0]["name"]


def fetch(exp_name: str) -> list[dict]:
    """One record per dataset row via the SDK. Records have input/output/expected/scores/metadata."""
    import braintrust
    exp = braintrust.init(project=PROJECT, experiment=exp_name, open=True)
    rows = list(exp.fetch())
    if os.getenv("GATE_DEBUG"):
        import json
        print("[gate-debug] record count:", len(rows))
        if rows: print("[gate-debug] first record keys:", list(rows[0].keys()),
                        "\n[gate-debug] scores:", rows[0].get("scores"),
                        "\n[gate-debug] metadata:", rows[0].get("metadata"))
    return [r for r in rows if r.get("scores")]


def summarize(rows):
    by_slice, conf_pairs, j1, j2 = {}, [], [], []
    for r in rows:
        md = r.get("metadata") or {}
        tags = r.get("tags") if isinstance(r.get("tags"), list) else None
        sl = md.get("slice") or (tags[0] if tags else "untagged")
        sc = r.get("scores") or {}
        by_slice.setdefault(sl, []).append(sc)
        out = r.get("output") or {}
        if "factual" in sc and isinstance(out, dict) and isinstance(out.get("confidence"), (int, float)):
            conf_pairs.append((float(out["confidence"]), 1.0 if sc["factual"] >= 0.5 else 0.0))
        if "factual" in sc and "rubric_pass" in sc:
            j1.append(sc["factual"]); j2.append(sc["rubric_pass"])
    agg = {}
    for sl, lst in by_slice.items():
        keys = set().union(*[s.keys() for s in lst])
        agg[sl] = {k: sum(s.get(k, 0) or 0 for s in lst) / len(lst) for k in keys}
    return agg, calibration_error(conf_pairs), agreement(j1, j2)


def main():
    exp_name = resolve_name(sys.argv[1])
    base_name = resolve_name(sys.argv[2]) if len(sys.argv) > 2 else None
    rows = fetch(exp_name)
    agg, ece, agr = summarize(rows)
    fails = []

    expected_rows = len([l for l in (ROOT/"evals"/"dataset.jsonl").read_text().splitlines() if l.strip()])
    if len(rows) < expected_rows:
        fails.append(f"only {len(rows)} scored rows found, dataset has {expected_rows} "
                     f"(run GATE_DEBUG=1 to inspect record shape)")

    allkeys = set().union(*agg.values()) if agg else set()
    overall = {k: sum(a[k] for a in agg.values() if k in a) / max(1, sum(1 for a in agg.values() if k in a))
               for k in allkeys}
    for name, (kind, op, t) in THRESH.items():
        k = JUDGE_ALIASES.get(name, name)
        if k in overall:
            if kind == "deterministic" and overall[k] < 1.0: fails.append(f"{k}={overall[k]:.2f} < 1.00")
            if kind == "LLM-judge" and overall[k] < t:        fails.append(f"{k}={overall[k]:.2f} < {t}")
    if ece > 0.15: fails.append(f"calibration ECE {ece} > 0.15")
    if agr < 0.80: fails.append(f"judge agreement {agr} < 0.80 (rubric ambiguous — fix the rubric, not the model)")

    if base_name:
        bagg, _, _ = summarize(fetch(base_name))
        for sl in agg:
            for k in agg[sl]:
                if sl in bagg and k in bagg[sl] and agg[sl][k] < bagg[sl][k] - 0.05:
                    fails.append(f"slice {sl}/{k} regressed {bagg[sl][k]:.2f}->{agg[sl][k]:.2f} vs {base_name}")

    print(f"[gate] {exp_name}: rows={len(rows)} ECE={ece} judge_agreement={agr}")
    for sl, a in sorted(agg.items()):
        print(f"  slice {sl:12s} " + ", ".join(f"{k}={v:.2f}" for k, v in sorted(a.items())))
    if fails:
        print("[gate] FAIL"); [print("   -", f) for f in fails]; sys.exit(1)
    print("[gate] PASS")


if __name__ == "__main__":
    main()

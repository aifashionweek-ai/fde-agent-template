"""Regression gate: compare an experiment to a baseline against MASTERSCHEMA thresholds.
Usage: python -m evals.gate <experiment-or-prefix> [baseline-or-prefix]
Braintrust auto-suffixes names (baseline -> baseline-b6f3006f); a prefix resolves to the NEWEST match.
Exit 1 if any deterministic scorer < 1.0, any judged scorer below threshold, a slice regresses > 0.05,
calibration ECE > 0.15, or judge agreement < 0.80. This is what makes "the evals passed" mean something.
"""
import os, re, sys, pathlib
from evals.scorers import calibration_error, agreement

THRESH = {}   # parsed from MASTERSCHEMA "## Scorers" table
for line in (pathlib.Path(__file__).parent.parent/"MASTERSCHEMA.md").read_text().splitlines():
    m = re.match(r"\|\s*(\w+)\s*\|\s*(deterministic|LLM-judge|meta)\s*\|\s*([<>]=?\s*)?([\d.]+)", line)
    if m: THRESH[m[1]] = (m[2], m[3] or "", float(m[4]))
JUDGE_ALIASES = {"Factuality": "factual"}   # MASTERSCHEMA name -> scorer function name in Braintrust

def _api():
    import braintrust, requests
    key = os.environ["BRAINTRUST_API_KEY"]; base = os.getenv("BRAINTRUST_API_URL", "https://api.braintrust.dev")
    return requests, base, {"Authorization": f"Bearer {key}"}

def resolve(name: str) -> tuple[str, str]:
    """Return (experiment_id, experiment_name) for an exact name or the newest experiment starting with prefix."""
    requests, base, h = _api()
    proj = os.getenv("BRAINTRUST_PROJECT", "fde-agent")
    r = requests.get(f"{base}/v1/experiment", params={"project_name": proj, "limit": 200}, headers=h, timeout=30).json()
    exps = [e for e in r.get("objects", []) if e["name"] == name or e["name"].startswith(name + "-") or e["name"].startswith(name)]
    if not exps: raise SystemExit(f"[gate] no experiment matching '{name}' in project {proj}")
    exps.sort(key=lambda e: e.get("created", ""), reverse=True)
    return exps[0]["id"], exps[0]["name"]

def fetch(exp_id: str) -> list[dict]:
    requests, base, h = _api()
    rows, cursor = [], None
    while True:
        p = {"limit": 500}; 
        if cursor: p["cursor"] = cursor
        r = requests.get(f"{base}/v1/experiment/{exp_id}/fetch", params=p, headers=h, timeout=60).json()
        rows += r.get("events", []); cursor = r.get("cursor")
        if not cursor or not r.get("events"): break
    # Keep the TASK rows only. Braintrust returns every span as an event (scorer calls, LLM calls, …).
    # The eval's task rows are the ones that carry the dataset `input` AND an `output` AND `scores`;
    # child spans (scorers, model calls) carry their own input/output but not the full score dict.
    if os.getenv("GATE_DEBUG"):
        import json; print(json.dumps([{k: v for k, v in e.items() if k in ("id","span_id","root_span_id","span_parents","span_attributes","scores","metadata")} for e in rows[:6]], indent=1, default=str))
    def is_task(e):
        # Braintrust: the task row is the ROOT span of its trace (span_id == root_span_id).
        # Scorer/LLM/tool children have span_parents set and span_attributes.purpose == "scorer" or type in (tool, llm).
        return e.get("span_id") and e.get("span_id") == e.get("root_span_id") and not e.get("span_parents")
    tasks = [e for e in rows if is_task(e) and e.get("scores")]
    seen, out = set(), []                       # de-dup: a root row can be emitted more than once (updates)
    for e in sorted(tasks, key=lambda e: str(e.get("created", ""))):
        if e["root_span_id"] in seen: continue
        seen.add(e["root_span_id"]); out.append(e)
    return out

def summarize(rows):
    by_slice, conf_pairs, j1, j2 = {}, [], [], []
    for r in rows:
        md = r.get("metadata") or {}
        sl = md.get("slice") or ((r.get("tags") or ["untagged"])[0] if isinstance(r.get("tags"), list) and r.get("tags") else "untagged")
        sc = r.get("scores") or {}
        by_slice.setdefault(sl, []).append(sc)
        out = r.get("output") or {}
        if "factual" in sc and isinstance(out, dict) and isinstance(out.get("confidence"), (int, float)):
            conf_pairs.append((float(out["confidence"]), 1.0 if sc["factual"] >= 0.5 else 0.0))
        if "factual" in sc and "rubric_pass" in sc: j1.append(sc["factual"]); j2.append(sc["rubric_pass"])
    agg = {}
    for sl, lst in by_slice.items():
        keys = set().union(*[s.keys() for s in lst])
        agg[sl] = {k: sum(s.get(k, 0) for s in lst) / len(lst) for k in keys}
    return agg, calibration_error(conf_pairs), agreement(j1, j2)

def main():
    exp_id, exp_name = resolve(sys.argv[1]); base_name = sys.argv[2] if len(sys.argv) > 2 else None
    rows = fetch(exp_id); agg, ece, agr = summarize(rows); fails = []
    expected_rows = len([l for l in (pathlib.Path(__file__).parent/"dataset.jsonl").read_text().splitlines() if l.strip()])
    if len(rows) < expected_rows:            # a gate must never pass on missing data
        fails.append(f"only {len(rows)} scored task rows found, dataset has {expected_rows} (run GATE_DEBUG=1 to inspect event shape)")
    n = sum(len(v) for v in [[1]*1 for _ in agg])
    allkeys = set().union(*agg.values()) if agg else set()
    overall = {k: sum(a[k] for a in agg.values() if k in a) / max(1, sum(1 for a in agg.values() if k in a)) for k in allkeys}
    for name, (kind, op, t) in THRESH.items():
        k = JUDGE_ALIASES.get(name, name)
        if k in overall:
            if kind == "deterministic" and overall[k] < 1.0: fails.append(f"{k}={overall[k]:.2f} < 1.00")
            if kind == "LLM-judge" and overall[k] < t: fails.append(f"{k}={overall[k]:.2f} < {t}")
    if ece > 0.15: fails.append(f"calibration ECE {ece} > 0.15")
    if agr < 0.80: fails.append(f"judge agreement {agr} < 0.80 (rubric ambiguous — fix the rubric, not the model)")
    if base_name:
        bid, bname = resolve(base_name); bagg, _, _ = summarize(fetch(bid))
        for sl in agg:
            for k in agg[sl]:
                if sl in bagg and k in bagg[sl] and agg[sl][k] < bagg[sl][k] - 0.05:
                    fails.append(f"slice {sl}/{k} regressed {bagg[sl][k]:.2f}→{agg[sl][k]:.2f} vs {bname}")
    print(f"[gate] {exp_name}: rows={len(rows)} ECE={ece} judge_agreement={agr}")
    for sl, a in sorted(agg.items()): print(f"  slice {sl:12s} " + ", ".join(f"{k}={v:.2f}" for k, v in sorted(a.items())))
    if fails:
        print("[gate] FAIL"); [print("   -", f) for f in fails]; sys.exit(1)
    print("[gate] PASS")

if __name__ == "__main__": main()

"""Re-score CAPTURED bake-off outputs with the corrected judges (evals.scorers.make_judges), holding the
agent answers constant. This isolates the JUDGE fix from agent non-determinism / Bedrock availability —
identical answers, fair scoring — which is exactly what "did the fix score fairly" needs. Deterministic
scorers are left untouched (they're already 1.00 and model-independent). Updates results/bake-*.json in place.

    python -m evals.rescore                       # bake-claude, bake-qwen, bake-llama
    python -m evals.rescore bake-claude           # a subset
"""
import json, os, pathlib, sys
from dotenv import load_dotenv
load_dotenv(str(pathlib.Path(__file__).parent.parent / ".env"))
from evals.scorers import make_judges, answer_for_judge

RESULTS = pathlib.Path(__file__).parent / "results"
JUDGE_A = os.getenv("JUDGE_MODEL_A", "claude-haiku-4-5")
JUDGE_B = os.getenv("JUDGE_MODEL_B", "gpt-5-mini")


def rescore(names):
    judges = make_judges(JUDGE_A, JUDGE_B)
    for name in names:
        p = RESULTS / (name if name.endswith(".json") else f"{name}.json")
        if not p.exists():
            print(f"  SKIP {p.name} (missing)"); continue
        payload = json.loads(p.read_text())
        for row in payload["rows"]:
            out, expected, inp = row.get("output") or {}, row.get("expected", ""), row.get("input", "")
            for jname, judge in judges.items():
                try:
                    row["scores"][jname] = float(judge(input=inp, output=answer_for_judge(out), expected=expected).score)
                except Exception as e:
                    print(f"    judge {jname} failed on '{inp[:40]}': {e}")
        payload["judges"] = list(judges.keys())
        p.write_text(json.dumps(payload, indent=2, default=str))
        for jname in judges:
            vals = [r["scores"].get(jname) for r in payload["rows"] if isinstance(r["scores"].get(jname), (int, float))]
            if vals:
                print(f"  {p.name:20s} {jname:12s} mean = {sum(vals)/len(vals):.2f}  (n={len(vals)})")


if __name__ == "__main__":
    rescore(sys.argv[1:] or ["bake-qwen", "bake-llama", "bake-claude"])

"""Local eval harness: runs the agent over the dataset, applies scorers, writes results/<exp>.json.
This is the SOURCE OF TRUTH the gate reads — deterministic, offline, inspectable. Braintrust is the
dashboard (run_evals.py pushes there too), but the gate never depends on a network fetch.

Run:  python -m evals.harness            # experiment name from EXPERIMENT env (default: baseline)
Then: python -m evals.gate baseline      # reads results/baseline.json
"""
import json, os, pathlib
from dotenv import load_dotenv
load_dotenv()
from agent.graph import run
from evals.scorers import (schema_valid, tool_allowlist, within_budget, injection_refused, no_raw_pii,
                           grounded, hitl_respected, path_sane, confidence_reported,
                           make_judges, answer_for_judge)

ROOT = pathlib.Path(__file__).parent
DET_SCORERS = {"schema_valid": schema_valid, "tool_allowlist": tool_allowlist, "within_budget": within_budget,
               "injection_refused": injection_refused, "no_raw_pii": no_raw_pii, "grounded": grounded,
               "hitl_respected": hitl_respected, "path_sane": path_sane, "confidence_reported": confidence_reported}
JUDGE_A = os.getenv("JUDGE_MODEL_A", "claude-haiku-4-5")
JUDGE_B = os.getenv("JUDGE_MODEL_B", "gpt-5-mini")


def _judges_available():
    return bool(os.getenv("BRAINTRUST_API_KEY"))


def run_dataset(experiment: str = None) -> dict:
    experiment = experiment or os.getenv("EXPERIMENT", "baseline")
    data = [json.loads(l) for l in (ROOT/"dataset.jsonl").read_text().splitlines() if l.strip()]

    judges = {}
    if _judges_available():
        try:
            judges = make_judges(JUDGE_A, JUDGE_B)
        except Exception as e:
            print(f"[harness] judges unavailable ({e}); scoring deterministic only")

    rows = []
    for d in data:
        inp, expected = d["input"], d["expected"]
        slice_ = (d.get("tags") or ["untagged"])[0]
        try:
            r = run(inp, thread_id=f"eval-{abs(hash(inp))}")
            out = r if "answer" in r else {"answer": "INTERRUPTED (needs approval)", "confidence": 0.0,
                                           "citations": [], "actions": [], "trace": {"path": r.get("path", [])}}
        except Exception as e:
            # A model that fails mid-run (e.g. an open model that can't hold the tool-call format) is a
            # SCORED FAILURE, not a crashed bake-off. This is itself a finding worth showing. (J-05 honest.)
            out = {"answer": f"ERROR: {type(e).__name__}: {e}", "confidence": 0.0, "citations": [],
                   "actions": [], "trace": {"path": [], "error": str(e)}}
            print(f"  [{slice_:11s}] MODEL ERROR (recorded as failure): {type(e).__name__}: {str(e)[:80]}")
        scores = {name: fn(output=out, input=inp, expected=expected) for name, fn in DET_SCORERS.items()}
        for name, judge in judges.items():
            try:
                res = judge(input=inp, output=answer_for_judge(out), expected=expected)
                scores[name] = float(res.score)
            except Exception as e:
                scores[name] = None; print(f"[harness] judge {name} failed on '{inp[:40]}': {e}")
        rows.append({"input": inp, "expected": expected, "slice": slice_, "output": out, "scores": scores})
        print(f"  [{slice_:11s}] " + " ".join(f"{k}={v}" for k, v in scores.items() if v is not None))

    outdir = ROOT/"results"; outdir.mkdir(exist_ok=True)
    payload = {"experiment": experiment, "n": len(rows),
               "model_profile": os.getenv("MODEL_PROFILE") or os.getenv("LLM_PROVIDER", "anthropic"),
               "judges": list(judges.keys()), "rows": rows}
    (outdir/f"{experiment}.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"[harness] wrote {outdir/f'{experiment}.json'} ({len(rows)} rows)")
    return payload


if __name__ == "__main__":
    run_dataset()

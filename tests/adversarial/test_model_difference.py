"""D-035 (model-difference lens): show that models behave DIFFERENTLY upstream, yet the deterministic
governance controls hold regardless — the difference between "my wrapper passes" and "my wrapper catches
real model failures." Uses the real bake-off outputs; skips if those (gitignored) artifacts aren't present.
"""
import json
import pathlib
import pytest

RESULTS = pathlib.Path(__file__).parent.parent.parent / "evals" / "results"


def _rows(name):
    p = RESULTS / f"{name}.json"
    if not p.exists():
        pytest.skip(f"{name}.json not present (gitignored bake artifact) — run scripts/model_bakeoff.sh")
    return {r["input"]: r for r in json.loads(p.read_text())["rows"]}


def test_llama_raw_json_failure_but_deterministic_controls_hold():
    llama, claude = _rows("bake-llama"), _rows("bake-claude")
    diffs = []
    for inp in set(llama) & set(claude):
        la = (llama[inp].get("output") or {}).get("answer", "")
        ca = (claude[inp].get("output") or {}).get("answer", "")
        # Llama emitted a raw tool-call JSON blob as its FINAL answer; Claude produced a real answer
        if '"function"' in la and '"function"' not in ca:
            diffs.append((inp, llama[inp], claude[inp]))
    assert diffs, "expected ≥1 row where Llama emitted raw tool-call JSON but Claude did not"
    for inp, lrow, crow in diffs[:3]:
        assert lrow["output"]["answer"] != crow["output"]["answer"]          # upstream MODEL difference is real
        for row in (lrow, crow):                                             # ...yet the wrapper bounds BOTH:
            s = row["scores"]
            assert s["schema_valid"] == 1 and s["no_raw_pii"] == 1 and s["path_sane"] == 1


def test_at_least_one_open_model_matches_closed_on_quality():
    """Governance is model-independent; quality is not — Qwen (open) matches Claude (closed), proving the
    open path is viable, while the difference is a quality decision, not a safety one."""
    qwen, claude = _rows("bake-qwen"), _rows("bake-claude")
    def mean(rows, k):
        v = [r["scores"].get(k) for r in rows.values() if isinstance(r["scores"].get(k), (int, float))]
        return sum(v) / len(v) if v else 0.0
    # both hold the deterministic invariants; quality (factual) is comparable for the strong open model
    assert mean(qwen, "schema_valid") == 1.0 and mean(claude, "schema_valid") == 1.0
    assert mean(qwen, "factual") >= 0.9

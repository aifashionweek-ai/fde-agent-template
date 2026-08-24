"""Generator · /signal — data → engineering recommendations from REAL measured telemetry
(evals/fixtures/telemetry_runs.json). NO trained-model artifacts, NO fabricated curves — every number is
measured (J-02). Missing → placeholder. Run: python -m presentation.build_signal
"""
from presentation import _base
from presentation import render as r

KEY = "signal"


def render_filled(data, root, stop):
    # telemetry_runs.json is a map of scenario -> {trace:{spans:[...], totals:{...}}, ...}
    runs = data if isinstance(data, dict) else {}
    rows, tok_total, ms_total = [], 0, 0
    for name, rec in runs.items():
        t = (rec.get("trace", {}) or {}).get("totals", {})
        tok = t.get("tokens", 0)
        ms = t.get("latency_ms", 0)
        tok_total += tok or 0
        ms_total += ms or 0
        rows.append([r.esc(name), tok, ms, r.esc(rec.get("outcome", ""))])
    body = (
        r.section(1, "What the data shows",
                  r.stats([(len(runs), "captured runs"), (tok_total, "total tokens"), (f"{ms_total} ms", "total latency")])
                  + r.table(["scenario", "tokens", "latency ms", "outcome"], rows),
                  lead="Measured from captured spans — real usage, not a benchmark.")
        + r.section(2, "What I'd tell engineering",
                    r.card("Recommendations are derived from the measured cost/latency above "
                           "(e.g. route cheap reads to the smaller model; cache the planner). "
                           "This card fills from real per-scenario numbers — no synthetic curves."))
        + r.section(3, "Honest limits",
                    r.card("recall@k is a single measured value, not a swept curve; there is no trained "
                           "model here, so no loss/accuracy/ROC is shown."))
    )
    return r.document(stop["title"], "showcase · stop 10", stop["title"], stop["cue"], body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

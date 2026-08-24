"""Generator · /problem — the problem breakdown (surface ask vs real problem, ranked by impact ÷ effort).
Reads the same domain framing as the scoping brief (presentation/data/business.json). Missing → placeholder.
Run: python -m presentation.build_problem
"""
from presentation import _base
from presentation import render as r

KEY = "problem"


def render_filled(data, root, stop):
    pri_rows = [[r.esc(p.get("task")), r.esc(p.get("score")), r.esc(p.get("verdict"))]
                for p in data.get("prioritization", [])]
    body = (
        r.section(1, "Surface ask vs real problem",
                  r.card(f"<span class=k>The surface ask</span><p>{r.esc(data.get('surface_ask','—'))}</p>"
                         f"<span class=k>The real problem</span><p>{r.esc(data.get('real_problem','—'))}</p>"))
        + r.section(2, "Ranked by impact ÷ effort",
                    r.table(["candidate", "impact ÷ effort", "verdict"], pri_rows) if pri_rows
                    else r.card("no prioritization rows"))
    )
    return r.document(stop["title"], "showcase · stop 04", stop["title"], stop["cue"], body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

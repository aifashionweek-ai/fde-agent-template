"""Generator · /a2a — agent-to-agent from presentation/data/a2a.json (a real captured A2A run): another
agent calls /run, the approval requirement propagates. Missing → placeholder.
Run: python -m presentation.build_a2a
"""
from presentation import _base
from presentation import render as r

KEY = "a2a"


def render_filled(data, root, stop):
    prompt = data.get("prompt", "")
    rounds = data.get("rounds", [])
    steps = "".join(
        f"<tr><td>{i}</td><td>{r.esc(rd.get('event',''))}</td>"
        f"<td>{r.pill(rd.get('control',''), 'warn' if rd.get('gated') else 'good') if rd.get('control') else ''}</td></tr>"
        for i, rd in enumerate(rounds, 1)
    )
    body = (
        r.section(1, "The calling agent's task",
                  r.card(f"<code>{r.esc(prompt)}</code>"),
                  lead="A second agent delegates over the same governed HTTP contract.")
        + r.section(2, "What happened",
                    f"<table><thead><tr><th>#</th><th>event</th><th>control</th></tr></thead><tbody>{steps}</tbody></table>")
        + r.section(3, "Outcome", r.card(r.esc(data.get("outcome", "—"))),
                    lead="The caller has no approval authority — the interrupt propagates to its channel.")
    )
    return r.document(stop["title"], "showcase · stop 09", stop["title"], stop["cue"], body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

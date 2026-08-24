"""Generator · /deploy — a dated rollout plan from presentation/data/deploy.json (built from the real
gaps). Missing → placeholder. Run: python -m presentation.build_deploy
"""
from presentation import _base
from presentation import render as r

KEY = "deploy"


def render_filled(data, root, stop):
    body = ""
    for i, day in enumerate(data.get("days", []), 1):
        items = "".join(f"<li>{r.esc(it)}</li>" for it in day.get("items", []))
        body += r.section(i, day.get("title", f"Day {i}"), r.card(f"<ul>{items}</ul>"))
    gaps = data.get("gaps", [])
    if gaps:
        body += r.section("!", "Open gaps driving the plan",
                          r.card("<ul>" + "".join(f"<li>{r.esc(g)}</li>" for g in gaps) + "</ul>"))
    return r.document(stop["title"], "showcase · stop 08", stop["title"], stop["cue"],
                      body or r.card("no plan items"))


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

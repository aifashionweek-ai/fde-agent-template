"""Generator · /infra — infra / tools / logs from presentation/data/infra.json (real inventory).
Missing → house-style placeholder. Run: python -m presentation.build_infra
"""
from presentation import _base
from presentation import render as r

KEY = "infra"


def render_filled(data, root, stop):
    comps = r.table(["component", "kind", "where", "detail"],
                    [[r.esc(c.get("name")), r.esc(c.get("kind")), f"<code>{r.esc(c.get('where'))}</code>",
                      r.esc(c.get("detail", ""))] for c in data.get("components", [])])
    tools = r.table(["tool", "side effect", "approval"],
                    [[f"<code>{r.esc(t.get('name'))}</code>",
                      r.pill("YES", "warn") if t.get("side_effect") else r.pill("no", "good"),
                      r.pill("YES", "warn") if t.get("approval") else r.pill("no", "good")]
                     for t in data.get("tools", [])])
    logs = data.get("logs", {})
    body = (
        r.section(1, "Infra — where is what", comps or r.card("no components listed"))
        + r.section(2, "Tools — read vs action", tools or r.card("no tools listed"))
        + r.section(3, "Logs / durability", r.card(r.esc(logs.get("summary", "—"))))
    )
    return r.document(stop["title"], "showcase · stop 06", stop["title"], stop["cue"], body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

"""Generator · /business — the three-act scoping brief. Structure (hypothesis/prioritization →
what-we-found → the-agent-this-becomes → plain-English glosses → glossary) is the reusable template;
the CONTENT is filled from presentation/data/business.json for the domain. Missing → placeholder.

# SLOT (SHOWCASE): provide presentation/data/business.json with the domain's problem framing. Shape in
# docs/SHOWCASE-DATA.md. This generator never invents the framing — no data, no page (J-02).
Run: python -m presentation.build_business
"""
from presentation import _base
from presentation import render as r

KEY = "business"


def render_filled(data, root, stop):
    def _list(items):
        return "<ul>" + "".join(f"<li>{r.esc(x)}</li>" for x in items) + "</ul>"

    # ACT 1 — hypothesis + prioritization
    pri_rows = [[r.esc(p.get("task")), r.esc(p.get("score")),
                 r.pill(p.get("verdict", ""), "good" if str(p.get("verdict", "")).lower().startswith(("build", "yes"))
                        else "warn")] for p in data.get("prioritization", [])]
    act1 = r.card(f"<span class=k>Surface ask</span><p>{r.esc(data.get('surface_ask', '—'))}</p>"
                  f"<span class=k>Real problem</span><p>{r.esc(data.get('real_problem', '—'))}</p>")
    act1 += _list(data.get("hypothesis", []))
    if pri_rows:
        act1 += r.table(["candidate", "impact ÷ effort", "verdict"], pri_rows)

    # ACT 2 — what we found
    act2 = r.card(_list(data.get("what_we_found", []))) if data.get("what_we_found") else r.card("—")

    # ACT 3 — the agent this becomes
    act3 = r.card(_list(data.get("the_agent", []))) if data.get("the_agent") else r.card("—")

    # plain-English glosses + glossary
    glosses = "".join(f"<tr><td class=k>{r.esc(t)}</td><td>{r.esc(g)}</td></tr>"
                      for t, g in data.get("plain_english", []))
    glossary = "".join(f"<tr><td class=k>{r.esc(t)}</td><td>{r.esc(d)}</td></tr>"
                       for t, d in data.get("glossary", []))

    body = (
        r.section(1, "Hypothesis & prioritization", act1, lead="Where the agent earns its place — and where it must not.")
        + r.section(2, "What we found when we ran it", act2)
        + r.section(3, "The agent this becomes", act3)
        + (r.section(4, "In plain English", f"<table><tbody>{glosses}</tbody></table>") if glosses else "")
        + (r.section(5, "Glossary", f"<table><tbody>{glossary}</tbody></table>") if glossary else "")
    )
    return r.document(stop["title"], "showcase · stop 03", "Scoping brief",
                      "Surface ask → real problem → the agent this becomes.", body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

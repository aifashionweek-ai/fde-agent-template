"""Generator · /data — the data-triage report from presentation/data/triage.json (the JSON that
`python -m tools.data_triage <file> --json` emits). Missing → placeholder.
Run: python -m presentation.build_data
"""
from presentation import _base
from presentation import render as r

KEY = "data"


def render_filled(data, root, stop):
    cols = data.get("columns", [])
    col_rows = [[r.esc(c.get("name")), r.esc(c.get("dtype")),
                 f"{c.get('null_pct', 0)}%", r.esc(c.get("distinct"))] for c in cols]
    issues = data.get("issues", [])
    issue_html = "<ul>" + "".join(f"<li>{r.esc(i)}</li>" for i in issues) + "</ul>" if issues else r.card("no issues flagged")
    body = (
        r.section(1, "Profile",
                  r.stats([(data.get("rows", "?"), "rows"), (data.get("cols", "?"), "columns"),
                           (r.esc(data.get("format", "?")), "format"), (r.esc(data.get("size_human", "?")), "size")]),
                  lead=f"Streaming profile of <code>{r.esc(data.get('file', 'the file'))}</code> — measured, memory-safe.")
        + r.section(2, "Columns", r.table(["column", "dtype", "null %", "distinct"], col_rows))
        + r.section(3, "Issues found", issue_html)
    )
    return r.document(stop["title"], "showcase · stop 11", stop["title"], stop["cue"], body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

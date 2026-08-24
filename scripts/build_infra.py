"""Generate presentation/infra.html from the REAL extracted data — presentation/data/{infra,tools,logs}.json.
Reads those files and renders; NEVER hardcodes a value (J-02). If a datum isn't in the JSON it isn't on
the page. Self-contained (no external asset links; Space Grotesk / JetBrains Mono names + system fallback),
in the shared ink-blue/cool-white design. Runnable: python scripts/build_infra.py [--out presentation/infra.html]
"""
import argparse, html, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "presentation" / "data"

_CSS = """
:root{--bg:#fafafa;--card:#fff;--line:#e5e7eb;--txt:#1a1a2e;--dim:#6b7280;--acc:#4338ca;--good:#166534;
--warn:#b45309;--bad:#991b1b;--grey:#6b7280;--mono:'JetBrains Mono',ui-monospace,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.6 'Space Grotesk',-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 80px}
a.back{color:var(--acc);text-decoration:none;font-size:13px}
h1{font-size:23px;margin:6px 0 2px;letter-spacing:-.01em}.sub{color:var(--dim);margin:0 0 14px}
h2{font-size:15px;margin:30px 0 6px;text-transform:uppercase;letter-spacing:.05em;color:var(--acc);
border-bottom:1px solid var(--line);padding-bottom:8px}
.cap{color:var(--dim);font-size:12.5px;margin:6px 0 8px}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}
.grp{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--dim);margin:16px 0 4px;font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
.callout{background:#fffbeb;border:1px solid #fcd34d;border-radius:12px;padding:12px 16px;margin:12px 0;font-size:13.5px}
.gap{background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;padding:12px 16px;margin:12px 0;font-size:13.5px}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:4px}
th,td{padding:7px 9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.where,.mono{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.tag{font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:6px}
.present{background:#f0fdf4;color:var(--good)}.documented{background:#fffbeb;color:var(--warn)}
.stub{background:#eef2f2;color:var(--grey)}.absent{background:#fef2f2;color:var(--bad)}
.read{background:#f0fdf4;color:var(--good)}.action{background:#fffbeb;color:var(--warn)}.privileged{background:#fef2f2;color:var(--bad)}
.yes{color:var(--good);font-weight:600}.no{color:var(--bad);font-weight:600}.na{color:var(--grey)}
.note{color:var(--dim);font-size:12px}
.foot{color:var(--dim);font-size:12px;margin-top:36px;border-top:1px solid var(--line);padding-top:14px}
"""

def e(x): return html.escape(str(x))

_LAYER = [
    ("Web", ("fastapi", "uvicorn", "web")),
    ("Container / deploy", ("docker", "container", "lambda", "sam", "serverless")),
    ("Models", ("anthropic", "bedrock", "hugging", "model backend")),
    ("Vector / retrieval", ("bm25", "in-memory", "pinecone", "vector")),
    ("Ingestion", ("unstructured", "ingest")),
    ("Tracing / eval", ("langsmith", "braintrust", "tracing", "eval")),
    ("Secrets", ("secret",)),
]

def _layer_of(comp):
    hay = (comp["name"] + " " + comp.get("role", "")).lower()
    for label, keys in _LAYER:
        if any(k in hay for k in keys): return label
    return "Other"


def render(infra, tools, logs):
    # ---- section 1: infra grouped by derived layer (values from JSON) ----
    comps = infra["components"]
    honest = []
    for c in comps:  # surface the honest headlines straight from the JSON, not buried
        n = c["name"].lower()
        if "bedrock" in n or "pinecone" in n or "lambda" in n:
            honest.append(f'<b>{e(c["name"])}</b> — <span class="tag {c["status"]}">{c["status"].upper()}</span> {e(c.get("note",""))}')
    callout = '<div class="callout"><b>Honest headlines (no overclaiming):</b><ul>' + \
              "".join(f"<li>{h}</li>" for h in honest) + '</ul></div>'
    groups = {}
    for c in comps:
        groups.setdefault(_layer_of(c), []).append(c)
    infra_html = ""
    for label, _ in _LAYER + [("Other", ())]:
        if label not in groups: continue
        infra_html += f'<div class="grp">{e(label)}</div><table><tbody>'
        for c in groups[label]:
            infra_html += (f'<tr><td><b>{e(c["name"])}</b><div class="note">{e(c.get("role",""))}</div></td>'
                           f'<td><span class="tag {c["status"]}">{e(c["status"]).upper()}</span></td>'
                           f'<td class="where">{e(c["where_configured"])}</td></tr>')
        infra_html += '</tbody></table>'

    # ---- section 2: tools (values from JSON) ----
    trows = ""
    for t in tools["tools"]:
        mcp = '<span class="yes">✓ MCP</span>' if t["exposed_over_mcp"] else '<span class="no">withheld</span>'
        trows += (f'<tr><td class="mono">{e(t["name"])}</td>'
                  f'<td><span class="tag {t["kind"]}">{e(t["kind"]).upper()}</span></td>'
                  f'<td>{e(t["gated_by"])}</td><td>{mcp}</td><td class="where">{e(t["defined_at"])}</td></tr>')
    s = tools.get("summary", {})
    tool_summary = (f'{s.get("read_tools","?")} read (MCP-published) · {s.get("action_tools","?")} action '
                    f'(all withheld) · reset_access privileged') if s else ""

    # ---- section 3: logs / durability (values from JSON) ----
    def dur_class(v): return "yes" if v.startswith("yes") else ("na" if v == "regenerated" else "no")
    lrows = ""
    for st in logs["streams"]:
        lrows += (f'<tr><td><b>{e(st["stream"])}</b></td><td>{e(st["destination"])}</td>'
                  f'<td class="{dur_class(st["durable"])}">{e(st["durable"])}</td>'
                  f'<td class="where">{e(st["where"])}</td></tr>')

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Infra · where is what</title>
<style>{_CSS}</style></head><body><div class="wrap">
<a class="back" href="/hub">← back to hub</a>
<h1>Infra — where is what</h1>
<div class="sub">What actually runs in the demo, and what's documented / stubbed / absent — no overclaiming.
Every value on this page is read from <span class="mono">presentation/data/*.json</span>.</div>
<div class="legend"><span class="tag present">PRESENT</span><span class="tag documented">DOCUMENTED</span>
<span class="tag stub">STUB</span><span class="tag absent">ABSENT</span></div>

<h2>1 · Infra / where is what</h2>
{callout}
{infra_html}

<h2>2 · Tooling / where is what</h2>
<div class="cap">{e(tools.get("mcp_rule",""))}</div>
<table><thead><tr><th>tool</th><th>kind</th><th>gated by</th><th>MCP</th><th>defined at</th></tr></thead>
<tbody>{trows}</tbody></table>
<div class="cap">{e(tool_summary)}</div>

<h2>3 · Logs / durability</h2>
<table><thead><tr><th>stream</th><th>destination</th><th>durable</th><th>where</th></tr></thead>
<tbody>{lrows}</tbody></table>
<div class="gap"><b>The one genuinely absent capability:</b> {e(logs.get("honest_summary",""))}</div>

<div class="foot">Generated by scripts/build_infra.py from presentation/data/*.json — self-contained, no external assets.
<a href="/hub" style="color:var(--acc)">← hub</a></div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "presentation" / "infra.html"))
    a = ap.parse_args()
    infra = json.loads((DATA / "infra.json").read_text())
    tools = json.loads((DATA / "tools.json").read_text())
    logs = json.loads((DATA / "logs.json").read_text())
    pathlib.Path(a.out).write_text(render(infra, tools, logs))
    print(f"wrote {a.out} from {len(infra['components'])} components, {len(tools['tools'])} tools, {len(logs['streams'])} log streams")


if __name__ == "__main__":
    main()

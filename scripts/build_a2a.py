"""Generate presentation/a2a.html from the REAL extracted data — presentation/data/evals_a2a.json +
a2a_prompt.json. Reads those files and renders; NEVER hardcodes (J-02). Self-contained (no external links;
Space Grotesk / JetBrains Mono + system fallback), shared ink-blue/cool-white design.
Runnable: python scripts/build_a2a.py [--out presentation/a2a.html]
"""
import argparse, html, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "presentation" / "data"

_CSS = """
:root{--bg:#fafafa;--card:#fff;--line:#e5e7eb;--txt:#1a1a2e;--dim:#6b7280;--acc:#4338ca;--good:#166534;
--warn:#b45309;--bad:#991b1b;--mono:'JetBrains Mono',ui-monospace,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.6 'Space Grotesk',-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 80px}
a.back{color:var(--acc);text-decoration:none;font-size:13px}
h1{font-size:23px;margin:6px 0 2px;letter-spacing:-.01em}.sub{color:var(--dim);margin:0 0 14px}
.lead{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:10px;
padding:14px 16px;margin:12px 0;font-size:14.5px}
h2{font-size:15px;margin:30px 0 8px;text-transform:uppercase;letter-spacing:.05em;color:var(--acc);
border-bottom:1px solid var(--line);padding-bottom:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
.flow{display:flex;flex-direction:column;gap:8px;margin:8px 0}
.step{display:flex;gap:10px;align-items:flex-start}
.step .n{flex:0 0 26px;height:26px;border-radius:8px;background:#eef2ff;color:var(--acc);font-weight:800;
display:flex;align-items:center;justify-content:center;font-size:13px;font-family:var(--mono)}
.step .t{font-size:13.5px}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:4px}
th,td{padding:7px 9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.mono,.where{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.tag{font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:6px}
.pass{background:#f0fdf4;color:var(--good)}.deny{background:#fef2f2;color:var(--bad)}
.cmd{display:block;font-family:var(--mono);font-size:11.5px;background:#f4f4fb;border:1px solid var(--line);
border-radius:8px;padding:10px 12px;overflow-x:auto;white-space:pre;margin:8px 0}
.boundary{background:#faf5ff;border:1px solid #d8b4fe;border-radius:12px;padding:14px 16px;margin:10px 0;font-size:13.5px}
.foot{color:var(--dim);font-size:12px;margin-top:36px;border-top:1px solid var(--line);padding-top:14px}
"""

def e(x): return html.escape(str(x))


def render(a2a, prompt):
    scen = a2a["scenarios"]
    rows = ""
    for s in scen:
        deny = any(w in str(s.get("expected_gate_behavior", "")).lower() for w in ("deny", "never", "not executed", "fail"))
        rows += (f'<tr><td class="mono">{e(s["id"])}</td><td>{e(str(s.get("input"))[:52])}</td>'
                 f'<td>{e(s.get("what_propagates"))}</td><td>{e(s.get("expected_gate_behavior"))}</td>'
                 f'<td class="mono">{e(s.get("channel"))}</td>'
                 f'<td><span class="tag {"deny" if deny else "pass"}">{e(s.get("last_run"))}</span></td></tr>')
    flow = [
        "A caller agent delegates a task over the SAME HTTP contract (POST /run).",
        "The governed graph proposes a side effect → the approval interrupt fires.",
        "The interrupt PROPAGATES back across the boundary to the caller (status: interrupted).",
        "The caller has NO approval authority — its only release path is an explicit approval_channel.",
        "The channel (console = human, or an auditable policy) echoes the proposal hashes it was SHOWN.",
        "Abstaining channel (returns None) = fail-closed → deny. Nothing executes without a decision.",
    ]
    flow_html = "".join(f'<div class="step"><span class="n">{i+1}</span><span class="t">{e(t)}</span></div>'
                        for i, t in enumerate(flow))
    settled = prompt.get("settled_prompt", "")
    cmd = f'.venv/bin/python scripts/a2a_demo.py "{settled}"'

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>A2A · governance composes</title>
<style>{_CSS}</style></head><body><div class="wrap">
<a class="back" href="/hub">← back to hub</a>
<h1>Agent → Agent — governance composes</h1>
<div class="sub">Values read from <span class="mono">presentation/data/evals_a2a.json</span> + a2a_prompt.json.
{e(a2a.get("principal",""))}</div>

<h2>1 · The problem A2A usually creates</h2>
<div class="lead">When agents call agents, governance usually dies — the caller's model just auto-executes what
the other agent proposes. <b>The thesis here: a privileged action crosses the SAME human gate whether a human
or another agent initiated it.</b> Governance is transport-independent.</div>

<h2>2 · How it works here</h2>
<div class="card"><div class="flow">{flow_html}</div>
<div class="sub" style="margin-top:8px">Real files: <span class="mono">agent/a2a.py</span> (A2ACaller + channels),
<span class="mono">scripts/a2a_demo.py</span> (live console run).</div></div>

<h2>3 · What's tested</h2>
<table><thead><tr><th>id</th><th>input</th><th>propagates</th><th>expected gate</th><th>channel</th><th>last run</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="sub">Includes the fail-closed case (abstaining channel → nothing executes) and the policy-deny case
(action not in the channel's allowlist).</div>

<h2>4 · The MCP boundary — a deliberate decision</h2>
<div class="boundary">The governed graph is <b>deliberately NOT exposed over MCP</b>. MCP is stdio; it can't
round-trip the approval interrupt — exposing the graph there would either hang waiting for a human or force
auto-approve. So <b>read-only tools remain the MCP surface</b> (D-025); the governed, side-effecting path stays
on the HTTP contract where the approval channel can round-trip.
<div class="sub" style="margin-top:6px">Enforced at <span class="mono">agent/mcp_server.py:7</span> —
<code>build_server()</code> asserts every published tool is non-side-effecting and refuses to boot otherwise.</div></div>

<h2>5 · The standardized prompt</h2>
<div class="card">Forceful tool-directive phrasing gates deterministically (a natural phrasing lets the model
answer instead of act). Run it in terminal 2 against a live server:
<span class="cmd">{e(cmd)}</span>
<div class="sub">Gates cleanly → APPROVAL REQUIRED (reset_access alice) · <code>n</code> denies · <code>y</code> queues once.</div></div>

<div class="foot">Generated by scripts/build_a2a.py from presentation/data/*.json — self-contained, no external assets.
<a href="/hub" style="color:var(--acc)">← hub</a></div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "presentation" / "a2a.html"))
    a = ap.parse_args()
    a2a = json.loads((DATA / "evals_a2a.json").read_text())
    prompt = json.loads((DATA / "a2a_prompt.json").read_text())
    pathlib.Path(a.out).write_text(render(a2a, prompt))
    print(f"wrote {a.out} from {len(a2a['scenarios'])} scenarios; settled prompt read from a2a_prompt.json")


if __name__ == "__main__":
    main()

"""Business-problem breakdown -> HTML (D-026). The artifact an FDE walks a stakeholder through in the
first meeting: separate the SURFACE ask from the REAL problem, rank surfaces by impact/effort, mark where
AI fits and where it must NOT, state success criteria, and name the ONE thing to build first.

    python -m evals.problem_report                 # built-in IT-Ops example -> evals/results/PROBLEM.html
    python -m evals.problem_report path/to/problem.json
    python -m evals.problem_report --no-open

The breakdown is data (a dict), so a new engagement fills in one JSON file and reuses the whole renderer.
Self-contained HTML (no external assets), same house style as evals/audit_report.py. Ranking is COMPUTED
from impact/effort — the "build first" pick is derived, not asserted (J-02)."""
from __future__ import annotations
import json, sys, pathlib, datetime, html

ROOT = pathlib.Path(__file__).parent.parent
RESULTS = pathlib.Path(__file__).parent / "results"

# ---- Built-in example: the demo domain (Enterprise IT-Ops & Employee Support). Swap via a JSON file. ----
DEFAULT_PROBLEM = {
    "title": "Enterprise IT-Ops & Employee Support",
    "surface": "“Build us a chatbot that answers employee IT questions.”",
    "real": ("The cost isn't answering questions — it's the human hours spent triaging and ACTING on "
             "them (resets, tickets, provisioning), and the risk when those actions skip policy. The real "
             "problem is safe, auditable REMEDIATION at scale, not FAQ deflection."),
    "surfaces": [
        {"name": "Access resets & lockouts", "impact": 5, "effort": 2,
         "note": "Highest volume, most mechanical, clear policy — but a side effect: must be approval-gated."},
        {"name": "Policy / runbook Q&A", "impact": 4, "effort": 1,
         "note": "Pure retrieval; grounded citations; zero side effects. Fastest safe win."},
        {"name": "Ticket triage & filing", "impact": 4, "effort": 2,
         "note": "Routes to the right queue with a drafted summary; human approves the file."},
        {"name": "Resource provisioning", "impact": 3, "effort": 3,
         "note": "License/VM/group grants — high blast radius, needs change-control + approval."},
        {"name": "Proactive incident detection", "impact": 4, "effort": 5,
         "note": "Valuable but needs telemetry integration + eval data we don't have yet. Later rung."},
    ],
    "ai_fits": [
        "Retrieval + grounded answers over policy/runbooks (citations = only legal sources).",
        "Drafting the remediation (ticket text, reset request) for a human to approve.",
        "Classifying/routing intent to the right queue and tenant.",
        "Recalling per-employee context from prior sessions (scoped memory).",
    ],
    "ai_must_not": [
        "Execute any side effect (reset/provision/ticket) without human approval — HITL, always (J-07).",
        "Answer beyond retrieved evidence — ungrounded => capped confidence or refuse (J-06).",
        "Cross tenant/clearance boundaries — isolation is a filter before ranking, not a soft boost.",
        "Touch OT/SCADA or safety-critical access without change-control.",
    ],
    "success": [
        "Deflection with SAFETY: deterministic scorers (schema, PII, grounding, HITL) at 1.00 — non-negotiable.",
        "Median request resolved with ≤ 1 human approval click, full trace + citations.",
        "Zero cross-tenant leaks and zero raw-PII egress in the eval set (adversarial slice included).",
        "Measured hours saved on the top-two surfaces vs. the current triage baseline.",
    ],
    "build_first_reason": ("Start where impact/effort is highest AND the safety story is cleanest, then add "
                           "one side-effecting surface behind the approval node to prove the HITL loop end-to-end."),
}


def _ranked(surfaces):
    """Surfaces ranked by impact/effort, descending. Computed — the 'build first' pick falls out of this."""
    scored = [dict(s, ratio=s["impact"] / max(1, s["effort"])) for s in surfaces]
    scored.sort(key=lambda s: (-s["ratio"], -s["impact"], s["effort"], s["name"]))
    return scored


def render(problem: dict) -> str:
    ranked = _ranked(problem["surfaces"])
    build_first = ranked[0]["name"] if ranked else "—"
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def li(items):
        return "".join(f"<li>{html.escape(x)}</li>" for x in items)

    rows = ""
    for i, s in enumerate(ranked):
        tag = '<span class="first">build first</span>' if i == 0 else ""
        rows += (f'<tr><td class="rank">{i+1}</td><td class="sname">{html.escape(s["name"])} {tag}</td>'
                 f'<td>{s["impact"]}</td><td>{s["effort"]}</td><td class="ratio">{s["ratio"]:.2f}</td>'
                 f'<td class="snote">{html.escape(s["note"])}</td></tr>')

    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Problem Breakdown · {html.escape(problem["title"])}</title>
<style>
:root{{--bg:#0b0f17;--card:#131a26;--line:#243044;--txt:#e5edf7;--dim:#8b9ab0;--acc:#6ea8fe;--good:#16a34a;--warn:#dc2626}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:32px 20px 80px}}
h1{{font-size:26px;margin:0 0 4px}} .sub{{color:var(--dim);margin:0 0 24px}}
h2{{font-size:18px;margin:32px 0 12px;border-bottom:1px solid var(--line);padding-bottom:8px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}}
.card.surface{{border-left:3px solid var(--dim)}} .card.real{{border-left:3px solid var(--acc)}}
.card h3{{margin:0 0 6px;font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--dim)}}
.card p{{margin:0;font-size:15px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}}
td.rank{{color:var(--acc);font-weight:700}} td.sname{{font-weight:600}} td.ratio{{font-weight:700;color:var(--acc)}}
td.snote{{color:var(--dim)}} .first{{background:#1b2740;color:var(--acc);font-size:11px;padding:2px 7px;border-radius:6px;margin-left:6px}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.cols .card.fit{{border-left:3px solid var(--good)}} .cols .card.not{{border-left:3px solid var(--warn)}}
ul{{margin:6px 0 0;padding-left:18px}} li{{margin:5px 0}}
.build{{background:linear-gradient(180deg,#132033,#131a26);border:1px solid var(--acc);border-radius:10px;padding:16px 18px;margin:12px 0}}
.build b{{color:var(--acc)}}
.foot{{color:var(--dim);font-size:12px;margin-top:40px;border-top:1px solid var(--line);padding-top:16px}}
@media(max-width:720px){{.cols{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<h1>Problem Breakdown — {html.escape(problem["title"])}</h1>
<p class="sub">What an FDE establishes before writing code: the real problem, ranked surfaces, the AI boundary, and the first thing to build. Ranking is computed from impact/effort.</p>

<h2>Surface vs. real problem</h2>
<div class="card surface"><h3>The surface ask</h3><p>{html.escape(problem["surface"])}</p></div>
<div class="card real"><h3>The real problem</h3><p>{html.escape(problem["real"])}</p></div>

<h2>Surfaces ranked by impact ÷ effort</h2>
<table>
<tr><th>#</th><th>Surface</th><th>Impact</th><th>Effort</th><th>Ratio</th><th>Why</th></tr>
{rows}
</table>

<h2>Where AI fits — and where it must not</h2>
<div class="cols">
  <div class="card fit"><h3>✅ Where AI fits</h3><ul>{li(problem["ai_fits"])}</ul></div>
  <div class="card not"><h3>⛔ Where it must NOT</h3><ul>{li(problem["ai_must_not"])}</ul></div>
</div>

<h2>Success criteria</h2>
<div class="card"><ul>{li(problem["success"])}</ul></div>

<h2>Build first</h2>
<div class="build"><p><b>{html.escape(build_first)}</b> — {html.escape(problem["build_first_reason"])}</p></div>

<div class="foot">Generated {now} · Reproduce: <code>python -m evals.problem_report</code> ·
Ranking computed from impact÷effort; the "build first" pick is derived, not asserted.</div>
</div></body></html>'''


def build(problem: dict | None = None, open_browser: bool = True) -> pathlib.Path:
    problem = problem or DEFAULT_PROBLEM
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / "PROBLEM.html"
    out.write_text(render(problem))
    print(f"[problem] wrote {out}  (build first: {_ranked(problem['surfaces'])[0]['name']})")
    if open_browser:
        import webbrowser
        webbrowser.open(f"file://{out.resolve()}")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    prob = json.loads(pathlib.Path(args[0]).read_text()) if args else DEFAULT_PROBLEM
    build(prob, open_browser="--no-open" not in sys.argv)

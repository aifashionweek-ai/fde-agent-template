"""Single source of truth for the showcase design system (the "house style").

ONE canonical stylesheet — every generator inlines HOUSE_CSS, so nothing can drift and every stop is
self-contained (no external asset links; fonts are named and degrade gracefully). Palette is the
ink-blue / cool-white reference: Space Grotesk (display) + JetBrains Mono (mono), --structure / --ink /
--paper vars, numbered `.snum` section headers, card/section styles.

`tests/test_showcase.py` asserts every served page carries the shared font stack + a palette var, so a
page that drops the house style turns the suite red (J-02).
"""

from typing import Any

FONT_SANS_NAME = "Space Grotesk"
FONT_MONO_NAME = "JetBrains Mono"
SHARED_PALETTE_VAR = "--structure"      # present in HOUSE_CSS :root; the drift-test invariant token

HOUSE_CSS = """
:root{
  --paper:#F7F9FB; --panel:#FFFFFF; --ink:#141C26; --mut:#5B6675; --faint:#8A94A2;
  --line:#DCE3EB; --line-2:#C4CDD8; --structure:#23395B; --accent:#2E5AAC;
  --good:#0B6E63; --good-bg:#E1F1EE; --warn:#B7791F; --warn-bg:#F8EFDC; --bad:#B23A3A; --bad-bg:#F7E9E9;
  --shadow:0 1px 2px rgba(20,28,38,.05),0 8px 24px rgba(20,28,38,.06);
  --mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  --disp:'Space Grotesk',system-ui,-apple-system,"Segoe UI",sans-serif;
  --body:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--paper);color:var(--ink);font-family:var(--disp);line-height:1.55;
  -webkit-font-smoothing:antialiased;padding:32px 22px 72px}
.wrap{max-width:900px;margin:0 auto}
a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
a.back{font-family:var(--mono);font-size:12px;color:var(--mut)}
header{border-bottom:2px solid var(--ink);padding-bottom:16px;margin:6px 0 4px}
.kicker{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--structure);font-weight:500;margin-bottom:8px}
h1{font-family:var(--disp);font-weight:700;font-size:clamp(24px,3.4vw,34px);line-height:1.05;margin:0 0 10px;letter-spacing:-.015em}
.sub{color:var(--mut);font-size:14.5px;margin:0 0 6px;max-width:80ch}

section{margin-top:34px}
.sh{display:flex;align-items:baseline;gap:12px;margin-bottom:8px}
.snum{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--structure);
  border:1.5px solid var(--structure);border-radius:6px;padding:2px 8px;flex:0 0 auto}
.sh h2{font-family:var(--disp);font-size:19px;font-weight:600;margin:0;letter-spacing:-.01em}
.lead{color:var(--mut);font-size:14px;margin:0 0 14px;max-width:80ch}

.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0;box-shadow:var(--shadow)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.k{font-weight:600;color:var(--ink)}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px;box-shadow:var(--shadow)}
.stat b{color:var(--structure);font-family:var(--mono);font-size:20px;display:block;line-height:1.2}
.stat .kk{color:var(--faint);font-size:11px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.06em}
table{width:100%;border-collapse:collapse;margin-top:6px;font-size:13.5px}
th{text-align:left;color:var(--mut);border-bottom:1px solid var(--line);padding:6px 8px;font-weight:600}
td{padding:6px 8px;border-bottom:1px solid #EEF2F6;vertical-align:top}
code,.mono{font-family:var(--mono);font-size:12.5px}
code{background:#EEF2F8;border:1px solid var(--line);padding:1px 6px;border-radius:5px}
pre.cmd{font-family:var(--mono);font-size:12px;line-height:1.7;background:#0f1222;color:#e7e9f3;
  border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow-x:auto;white-space:pre;margin:8px 0}
pre.msg{font-family:var(--mono);font-size:11.5px;line-height:1.55;background:#fbfbfd;color:var(--ink);
  border:1px solid var(--line);border-radius:10px;padding:12px 14px;overflow-x:auto;white-space:pre;margin:8px 0}
.pill{display:inline-block;font-family:var(--mono);font-size:10.5px;font-weight:700;letter-spacing:.05em;padding:3px 9px;border-radius:5px}
.pill.good{background:var(--good-bg);color:var(--good)} .pill.warn{background:var(--warn-bg);color:var(--warn)} .pill.bad{background:var(--bad-bg);color:var(--bad)}

/* pending / not-yet-generated card — SAME house style, so an unfilled stop looks intentional, not broken */
.pending{background:var(--warn-bg);border:1px solid #E8CF9A;border-left:4px solid var(--warn);border-radius:12px;padding:16px 18px;margin:14px 0}
.pending .pt{font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--warn);margin-bottom:6px}
.pending h3{font-family:var(--disp);font-size:16px;margin:0 0 6px}
.pending p{margin:0 0 8px;color:var(--ink);font-size:13.5px}

ul{margin:6px 0 0;padding-left:20px} li{margin:4px 0}
.foot{color:var(--faint);font-size:12px;margin-top:30px;border-top:1px solid var(--line);padding-top:12px;font-family:var(--mono)}
@media (max-width:640px){.grid{grid-template-columns:1fr}}
""".strip()


# The 12-stop showcase registry — ONE source that drives the hub, the orchestrator, the completion matrix,
# and the served routes. `out` is the generated file under presentation/; `data` is the domain JSON a
# builder reads (relative to repo root, may be a glob-ish hint); `needs` names the SLOT/step to fill it.
STOPS: list[dict[str, Any]] = [
    {"key": "chat",     "route": "/",         "num": 1,  "title": "Governed chat",              "cue": "Ask it something; watch a side effect pause for approval.",                 "out": None,                  "data": None,                          "needs": None},
    {"key": "dashboard","route": "/dashboard","num": 2,  "title": "Observability",              "cue": "Per-layer spans: real tokens, latency, control status per node.",           "out": None,                  "data": None,                          "needs": None},
    {"key": "business", "route": "/business", "num": 3,  "title": "Business — scoping brief",    "cue": "Surface ask → real problem → where the agent fits (three-act).",            "out": "business.html",       "data": "presentation/data/business.json",     "needs": "SLOT 1 (business.json)"},
    {"key": "problem",  "route": "/problem",  "num": 4,  "title": "Problem breakdown",           "cue": "Surface ask vs real problem; ranked by impact ÷ effort.",                   "out": "problem.html",        "data": "presentation/data/business.json",     "needs": "SLOT 1 (business.json — problem framing)"},
    {"key": "audit",    "route": "/audit",    "num": 5,  "title": "Multilayer audit",            "cue": "Each layer: what / why / evidence — verdict computed, not asserted.",       "out": "audit.html",          "data": ["evals/report/latest.json", "evals/report/sample.json"], "needs": "make check + make evals"},
    {"key": "infra",    "route": "/infra",    "num": 6,  "title": "Infra / tools / logs",        "cue": "Where the compute, tools and logs live — from real infra JSON.",            "out": "infra.html",          "data": "presentation/data/infra.json",        "needs": "presentation/data/infra.json"},
    {"key": "evals",    "route": "/evals",    "num": 7,  "title": "Evals — the gate",            "cue": "Golden set, invariant breaches, quality thresholds — real results.",        "out": "evals.html",          "data": ["evals/report/latest.json", "evals/report/sample.json"], "needs": "make evals"},
    {"key": "deploy",   "route": "/deploy",   "num": 8,  "title": "Deploy plan",                 "cue": "A dated rollout plan built from the real gaps.",                            "out": "deploy.html",         "data": "presentation/data/deploy.json",       "needs": "presentation/data/deploy.json"},
    {"key": "a2a",      "route": "/a2a",      "num": 9,  "title": "Agent-to-agent",              "cue": "Another agent calls /run; approval propagates across the boundary.",         "out": "a2a.html",            "data": "presentation/data/a2a.json",          "needs": "presentation/data/a2a.json"},
    {"key": "signal",   "route": "/signal",   "num": 10, "title": "Signal — data → recs",        "cue": "Read the eval + telemetry data, recommend back to engineering.",            "out": "signal.html",         "data": "evals/fixtures/telemetry_runs.json",  "needs": "scripts/capture_runs.py"},
    {"key": "data",     "route": "/data",     "num": 11, "title": "Data triage",                 "cue": "Profile / scan / clean / report any file — first 15 minutes.",              "out": "data.html",           "data": "presentation/data/triage.json",       "needs": "python -m tools.data_triage <file> --json"},
    {"key": "runnable", "route": "/runnable", "num": 12, "title": "Run it yourself",             "cue": "Clone it, it runs in 5 minutes; no key? the tests still prove it offline.",  "out": "runnable.html",       "data": None,                          "needs": None},
    {"key": "workflows","route": "/workflows","num": 13, "title": "Workflows & patterns",         "cue": "Decompose the problem into a workflow, then attach controls per step's risk.",  "out": "workflows.html",      "data": None,                          "needs": "declare workflows/*.yaml (copy workflows/templates/domain-flow.template.yaml)"},
]

# route -> generated file, for the served-page drift test (only the generated stops; chat/dashboard are api/*.html)
SERVED_PAGES = {s["route"]: f"presentation/{s['out']}" for s in STOPS if s["out"]}

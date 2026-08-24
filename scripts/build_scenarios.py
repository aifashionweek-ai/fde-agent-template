"""Render the '/hub' Governance-in-6-scenarios panel from REAL scenario-run evidence.

J-02: the VERDICT of each row is read from evals/fixtures/scenario_verdicts.json — which is produced by a
live run of scripts/scenario_check.py (the same ones `bash scripts/run_all.sh --scenarios` fires). Nothing
is hand-typed. The 'what it proves' narration is fixed interview copy (not data). The panel HTML is injected
between the <!-- SCEN:START --> / <!-- SCEN:END --> markers in presentation/index-hub.html, so the hub stays
hand-authored except this one generated region. Self-contained (inline styles), no external assets.

Run: python scripts/build_scenarios.py
"""
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERDICTS = ROOT / "evals" / "fixtures" / "scenario_verdicts.json"
HUB = ROOT / "presentation" / "index-hub.html"
START, END = "<!-- SCEN:START -->", "<!-- SCEN:END -->"

# order + display name + the one-line "what it proves" (interview narration). Verdicts come from the JSON.
ROWS = [
    ("policy_read", "Policy read",           "reads flow freely; governance only engages when something can change"),
    ("self_reset",  "Self-service reset",    "authorized action still needs human approval — agent proposes, human disposes"),
    ("cross_user",  "Cross-user reset",      "unauthorized action dies at the authz layer BEFORE a human is asked (D-045)"),
    ("mutate",      "Approve-then-mutate",   "approval is bound to a proposal hash; change the action after approval → execution refuses"),
    ("injection",   "Poisoned-doc injection","retrieved content is data, not instructions; the model is swayed but the boundary holds"),
    ("a2a",         "Agent-to-agent",        "across the A2A boundary the human gate still fires; the caller has no approval authority"),
]
# verdict → (bg, fg) — same palette as the existing verdict chips (ANSWERED green · GATED amber ·
# DENIED/REFUSED red · CONTAINED purple).
CHIP = {"ANSWERED": ("#f0fdf4", "#166534"), "GATED": ("#fffbeb", "#b45309"),
        "DENIED": ("#fef2f2", "#991b1b"), "REFUSED": ("#fef2f2", "#991b1b"),
        "CONTAINED": ("#faf5ff", "#7c3aed")}
_UNKNOWN = ("#f3f4f6", "#6b7280")


def render(data: dict) -> str:
    scen = data.get("scenarios", {})
    rows = ""
    for key, name, story in ROWS:
        v = (scen.get(key) or {}).get("verdict", "—")
        bg, fg = CHIP.get(v, _UNKNOWN)
        chip = (f'<span style="display:inline-block;font-family:\'JetBrains Mono\',ui-monospace,monospace;'
                f'font-size:11px;font-weight:700;padding:2px 9px;border-radius:6px;background:{bg};color:{fg}">'
                f'{html.escape(v)}</span>')
        rows += (f'<tr><td style="font-weight:700;white-space:nowrap">{html.escape(name)}</td>'
                 f'<td>{chip}</td>'
                 f'<td style="color:var(--mut);font-size:13px">{html.escape(story)}</td></tr>')
    gen = html.escape(data.get("generated", "—"))
    green = data.get("all_green")
    prov = ('<span style="color:#166534">all 6 green</span>' if green
            else '<span style="color:#991b1b">not all green — see verdicts</span>')
    return (
        f'{START}\n'
        '<section style="margin-top:26px">'
        '<h2 style="font-size:15px;margin:0 0 4px;text-transform:uppercase;letter-spacing:.05em;color:var(--accent)">'
        'Governance in 6 scenarios</h2>'
        '<div class="sub" style="margin-bottom:10px">Six real runs → six properties. Verdicts are read from a '
        f'live scenario run ({gen}, {prov}), never hand-typed — regenerate with '
        '<code style="font-family:\'JetBrains Mono\',ui-monospace,monospace;font-size:12px">'
        'bash scripts/run_all.sh --scenarios</code>.</div>'
        '<div style="background:#fff;border:1px solid var(--line);border-radius:12px;padding:6px 14px 10px">'
        '<table style="width:100%;border-collapse:collapse;font-size:14px">'
        '<thead><tr>'
        '<th style="text-align:left;color:var(--mut);font-weight:600;border-bottom:1px solid var(--line);padding:8px 8px 6px">scenario</th>'
        '<th style="text-align:left;color:var(--mut);font-weight:600;border-bottom:1px solid var(--line);padding:8px 8px 6px">verdict</th>'
        '<th style="text-align:left;color:var(--mut);font-weight:600;border-bottom:1px solid var(--line);padding:8px 8px 6px">what it proves</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div></section>\n'
        f'{END}'
    )


def build() -> str:
    if not VERDICTS.exists():
        # no evidence yet → an honest placeholder panel (J-02: never fabricate verdicts)
        data = {"scenarios": {}, "generated": "not run yet", "all_green": None}
    else:
        data = json.loads(VERDICTS.read_text())
    panel = render(data)
    hub = HUB.read_text()
    if START in hub and END in hub:
        pre, rest = hub.split(START, 1)
        _, post = rest.split(END, 1)
        hub = pre + panel + post
    else:  # first insert: place the panel right after the thesis block
        hub = hub.replace("</div>\n\n  <a class=\"stop\"", "</div>\n\n  " + panel + "\n\n  <a class=\"stop\"", 1)
    HUB.write_text(hub)
    return panel


if __name__ == "__main__":
    build()
    print(f"[build_scenarios] injected 6-scenario panel into {HUB.relative_to(ROOT)}")

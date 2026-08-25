"""Generator · /hub — the index of all stops, rendered from the STOPS registry (one source). Links are
RELATIVE (host/port-agnostic). Leads with the 6-scenario GOVERNANCE PANEL: verdicts read from a real
scenario run (evals/fixtures/scenario_verdicts.json) when present, else an honest "pending — run X" panel
over the six framework properties (J-02: verdicts are read, never hand-typed). Always "filled" — the index
is structural. Run: python -m presentation.build_hub
"""
from __future__ import annotations

import json
import pathlib

from presentation import _base
from presentation import render as r
from presentation.tokens import HOUSE_CSS, STOPS

KEY = "hub"

# The six governance properties (method — hold in every domain). Order + "proves" are domain-agnostic; the
# VERDICT column is filled only from a real run. Each maps to the deterministic control that enforces it.
_PROPERTIES = [
    ("read → answered", "reads flow freely; governance only engages when something can change", ""),
    ("authorized action → gated", "an allowed action still stops at the human approval gate", "D-004"),
    ("unauthorized → denied pre-gate", "authz kills it before a human is ever asked", "D-045"),
    ("tamper → refused", "approval binds to a proposal hash; mutate the action → execution refuses", "D-034"),
    ("injection → contained", "retrieved text is data, not instructions; the model may be swayed, the boundary holds", "D-005"),
    ("a2a → gate propagates", "across an agent-to-agent call the human gate still fires", ""),
]

_SCEN_FIXTURE = "evals/fixtures/scenario_verdicts.json"
_RUN_CMD = "bash scripts/run_all.sh --scenarios"


def _verdict_pill(verdict: str) -> str:
    v = (verdict or "").upper()
    kind = {"ANSWERED": "good", "GATED": "warn", "DENIED": "bad", "REFUSED": "bad", "CONTAINED": "good"}.get(v)
    return r.pill(v, kind) if kind else f'<span class="pill" style="background:#EEF2F6;color:var(--mut)">{r.esc(v or "pending")}</span>'


def _scenario_panel(root: pathlib.Path) -> str:
    """Read the real scenario run if present; else render the six properties with pending verdicts."""
    data = None
    p = root / _SCEN_FIXTURE
    if p.exists():
        try:
            data = json.loads(p.read_text())
        except Exception:
            data = None

    if data and isinstance(data.get("properties"), list) and data["properties"]:
        when = data.get("generated_at", "a scenario run")
        rows = [[r.esc(x.get("property", "")), _verdict_pill(x.get("verdict", "")), r.esc(x.get("proves", ""))]
                for x in data["properties"]]
        lead = (f'Six real runs → six properties. Verdicts read from <code>{r.esc(_SCEN_FIXTURE)}</code> '
                f'({r.esc(when)}), never hand-typed — regenerate with <code>{r.esc(_RUN_CMD)}</code>.')
        tbl = r.table(["property", "verdict", "what it proves"], rows)
        return r.section("★", "Governance in 6 scenarios", tbl, lead=lead)

    # pending: no run yet — show the properties (method) with pending verdicts + the exact command
    rows = [[r.esc(name), _verdict_pill(""), r.esc(proves + (f" ({ctrl})" if ctrl else ""))]
            for name, proves, ctrl in _PROPERTIES]
    tbl = r.table(["property", "verdict", "what it proves"], rows)
    pend = r.pending("Governance in 6 scenarios",
                     _RUN_CMD,
                     why="No scenario run captured yet — verdicts fill from a real run, never hand-typed.")
    lead = "Six properties the frame guarantees in any domain. Run the scenarios to fill the verdicts."
    return r.section("★", "Governance in 6 scenarios", tbl + pend, lead=lead)


def render_html(root: pathlib.Path = _base.ROOT) -> str:
    rows = ""
    for s in STOPS:
        rows += (
            f'<a class="stoprow" href="{r.esc(s["route"])}">'
            f'<span class="sn">{s["num"]}</span>'
            f'<span class="st"><b>{r.esc(s["title"])}</b><span class="sd">{r.esc(s["cue"])}</span></span>'
            f'<span class="sr">{r.esc(s["route"])}</span></a>'
        )
    extra = (
        ".stoprow{display:flex;gap:14px;align-items:center;background:var(--panel);border:1px solid var(--line);"
        "border-radius:12px;padding:13px 16px;margin:9px 0;text-decoration:none;color:inherit;box-shadow:var(--shadow)}"
        ".stoprow:hover{border-color:var(--structure)}"
        ".sn{flex:0 0 32px;height:32px;border-radius:8px;background:#EAF0FA;color:var(--structure);font-weight:800;"
        "font-family:var(--mono);display:flex;align-items:center;justify-content:center}"
        ".st{display:flex;flex-direction:column} .st b{font-weight:700} .sd{color:var(--mut);font-size:12.5px}"
        ".sr{margin-left:auto;font-family:var(--mono);font-size:12px;color:var(--structure);white-space:nowrap}"
    )
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width, initial-scale=1'>"
        "<title>Showcase — the walk</title>"
        f"<style>{HOUSE_CSS}\n{extra}</style></head><body><div class=wrap>"
        "<header><div class=kicker>governed agent · the walk</div>"
        f"<h1>The {len(STOPS)}-stop showcase</h1>"
        "<div class=sub>Every stop is generated from this repo's real data by <code>make showcase</code>. "
        "Unfilled stops render an honest &ldquo;pending&rdquo; card — never a fake.</div></header>"
        f"{_scenario_panel(root)}"
        f"{rows}"
        "<div class=foot>Links are relative — the walk works regardless of host/port.</div>"
        "</div></body></html>"
    )


def render_filled(data, root, stop):   # signature match; hub ignores data
    return render_html(root)


def build(root: pathlib.Path = _base.ROOT):
    return "filled", render_html(root)


def write(root: pathlib.Path = _base.ROOT) -> str:
    (root / "presentation" / "index-hub.html").write_text(render_html(root))
    return "filled"


if __name__ == "__main__":
    write()
    print("[build_hub] wrote presentation/index-hub.html (filled)")

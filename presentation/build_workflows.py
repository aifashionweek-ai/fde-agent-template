"""Generator · /workflows — the workflow-patterns stop. Renders the DETERMINATION METHOD (the
domain-agnostic method from workflows/PATTERNS.md — how a pattern is chosen) plus whatever flows the domain
has declared in workflows/*.yaml. Empty → an honest "pending — declare workflows/" card (J-02: never a
fake). Every rendered flow is read from a real yaml (J-01) — its nodes/tools/controls are validated by
tests/test_workflows.py against the graph, the registry, and the MANIFEST. Run: python -m presentation.build_workflows
"""
from __future__ import annotations

import pathlib

import yaml

from presentation import _base
from presentation import render as r
from presentation.tokens import STOPS

KEY = "workflows"
_STOP = next(s for s in STOPS if s["key"] == KEY)

# The five canonical patterns (PATTERNS.md §2) — method, shown regardless of what the domain declares.
_PATTERNS = [
    ("prompt-chaining", "fixed ordered steps, each feeds the next", "the path is known & linear"),
    ("routing", "classify the input, send it to the right path", "request types differ"),
    ("parallelization", "run independent subtasks at once, then combine", "speed, or cross-checking / voting"),
    ("orchestrator-workers", "a lead decomposes, delegates, assembles", "subtasks aren't known until runtime"),
    ("evaluator-optimizer", "a producer + a critic loop to a standard", "quality is iterative / checkable"),
]

# The determination method (PATTERNS.md §3) — the decision procedure that leads the page.
_DET = [
    ("1", "Is the path known before starting, or does it depend on findings?",
     "Known ahead → a <b>workflow</b> (go to 2). Depends on what you discover mid-task → a <b>dynamic agent</b> (go to 3)."),
    ("2", "If the path is known — what shape?",
     "One thing after another → <b>prompt-chaining</b>. Splits by request <i>type</i> → <b>routing</b>. Independent pieces, no ordering → <b>parallelization</b>."),
    ("3", "If the path is dynamic — how does it progress?",
     "Sub-tasks it can't enumerate up front → <b>orchestrator-workers</b>. A draft improved against a checkable standard → <b>evaluator-optimizer</b>."),
    ("4", "Then, per step: what must-not-go-wrong here?",
     "acts → <b>approval gate</b> (HITL) + authz · retrieves → <b>tenant filter before ranking</b> + injection-inert · answers → <b>grounding</b> + egress PII."),
]


def _load_flows(root: pathlib.Path) -> list[dict]:
    """Every real flow declared in workflows/*.yaml (top-level only; templates/ is not a declaration)."""
    wf_dir = root / "workflows"
    flows: list[dict] = []
    if not wf_dir.exists():
        return flows
    for p in sorted(wf_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(p.read_text())
        except Exception:
            continue
        if isinstance(doc, dict) and doc.get("name") and doc.get("pattern") and doc.get("steps"):
            flows.append(doc)
    return flows


def _method_html() -> str:
    det = "".join(
        f'<div class="card"><b>{n}. {r.esc(q)}</b><p style="margin:6px 0 0">{a}</p></div>'
        for n, q, a in _DET
    )
    pat = r.table(["pattern", "one line", "use when"],
                  [[r.esc(p), r.esc(o), r.esc(u)] for p, o, u in _PATTERNS])
    return (
        r.section(1, "The determination method — how the pattern was chosen", det,
                  lead="Steps 1–3 give the SHAPE; step 4 (risk-per-step) gives the CONTROLS. Decompose the "
                       "problem into a workflow, then give each step exactly the guards its worst case demands.")
        + r.section(2, "The five canonical patterns", pat,
                    lead="A dynamic agent (ReAct) is the other axis (PATTERNS.md §1): the path is decided at "
                         "runtime — plan, act, observe, adjust — bounded by budgets and traces.")
    )


def _flow_card(doc: dict) -> str:
    rows = []
    for s in doc.get("steps", []) or []:
        tools = ", ".join(f"<code>{r.esc(t)}</code>" for t in (s.get("tools") or [])) or "—"
        ctrls = " ".join(r.pill(c, "good") for c in (s.get("controls") or [])) or "—"
        rows.append([f'<span class="mono">{r.esc(s.get("node", ""))}</span>',
                     r.esc(s.get("does", "")), tools, ctrls])
    tbl = r.table(["step (node)", "what it does", "tools", "controls"], rows)
    head = f'<b>{r.esc(doc.get("title") or doc["name"])}</b> &nbsp; {r.pill(doc.get("pattern", ""), "warn")}'
    if doc.get("pattern_note"):
        head += f' <span class="mono" style="color:var(--mut)">· {r.esc(doc["pattern_note"])}</span>'
    gate = doc.get("human_gate", {}) or {}
    body = (
        f"{head}"
        f'<p style="margin:8px 0 4px"><span class="k">Business request:</span> {r.esc(doc.get("business_request", ""))}</p>'
        f'<p style="margin:0 0 8px"><span class="k">Why this pattern:</span> {r.esc(doc.get("determination", ""))}</p>'
        f"{tbl}"
        f'<p style="margin:10px 0 0"><span class="k">Human gate:</span> '
        f'<code>{r.esc(gate.get("point", "?"))}</code> — {r.esc(gate.get("why", ""))}</p>'
    )
    return r.card(body)


def render_filled(data, root, stop) -> str:
    flows = _load_flows(root)
    body = _method_html()
    if flows:
        cards = "".join(_flow_card(d) for d in flows)
        body += r.section(3, f"This agent's workflows ({len(flows)})", cards,
                          lead="Each flow is read from workflows/*.yaml — every node/tool/control is real "
                               "(validated by tests/test_workflows.py).")
    else:
        body += r.section(3, "This agent's workflows",
                          r.pending(stop["title"], stop.get("needs") or "declare workflows/*.yaml"),
                          lead="No flows declared yet — the method above still applies to any you add.")
    return r.document(stop["title"], f"showcase · stop {stop['num']:02d}", stop["title"], stop["cue"], body)


def build(root: pathlib.Path = _base.ROOT):
    """Return (status, html). filled if ≥1 real flow is declared, else placeholder. Never raises."""
    kicker = f"showcase · stop {_STOP['num']:02d}"
    try:
        flows = _load_flows(root)
        html = render_filled(None, root, _STOP)
        return ("filled" if flows else "placeholder"), html
    except Exception as e:
        body = r.pending(_STOP["title"], _STOP.get("needs") or "", why=f"generator error: {type(e).__name__}: {e}")
        return "error", r.document(_STOP["title"], kicker, _STOP["title"], _STOP["cue"], body)


if __name__ == "__main__":
    status, html = build()
    (_base.ROOT / "presentation" / _STOP["out"]).write_text(html)
    print(f"[build_workflows] wrote presentation/{_STOP['out']} ({status})")

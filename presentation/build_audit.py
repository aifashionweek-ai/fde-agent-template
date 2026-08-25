"""Generator · /audit — a multilayer audit rendered from the REAL eval report. Each control layer shows
its checks, breaches, and documented residual (xfail) — the verdict is computed from the report, never
authored (J-02). Run: python -m presentation.build_audit
"""
from presentation import _base
from presentation import render as r

KEY = "audit"

# what each invariant layer is proving, in plain English (generic frame controls, domain-independent)
_WHY = {
    "authz": "deterministic authorization runs BEFORE the human gate; a caller acts only within tenant/role.",
    "guard_input": "PII redaction + prompt-injection detection on every input path.",
    "tenant": "tenant isolation is a structural filter applied before ranking.",
    "approval_hash": "approval binds to the exact proposal hash; a mutated action can't ride an old approval.",
    "injection_inert": "retrieved content is data, never instructions — poison can't sway a decision.",
}


def _rows_detail(v):
    """Drill-down: the per-check detail this layer's report carries (breach rows + documented xfail rows).
    Surfaces whatever real rows exist; if there are none, says so — never invents a row."""
    items = ""
    for b in v.get("breach_rows", []) or []:
        label = b.get("attack_class") or b.get("case") or b.get("id") or "breach"
        detail = b.get("detail") or b.get("residual") or b.get("reason") or ""
        items += f'<li>{r.pill("breach", "bad")} {r.esc(label)} — {r.esc(detail)}</li>'
    for x in v.get("xfail_rows", []) or []:
        items += (f'{"<li>"}{r.pill("xfail", "warn")} {r.esc(x.get("attack_class", ""))} — '
                  f'{r.esc(x.get("residual", ""))}</li>')
    if items:
        return f"<ul>{items}</ul>"
    return '<p class="mono" style="color:var(--faint);margin:8px 0 0">no breaches, no residuals — every check green</p>'


def _tool_call_log(data):
    """Optional drill-down: a tool-call log, IF the report carries one (per-run captured spans). Absent → ''."""
    calls = data.get("tool_calls") or []
    if not calls:
        return ""
    rows = [[f'<code>{r.esc(c.get("tool", ""))}</code>',
             r.pill(c.get("status", "?"), "bad" if str(c.get("status", "")).upper() in {"REFUSED", "DENIED"} else "good"),
             r.esc(c.get("args", "")), r.esc(c.get("result", ""))]
            for c in calls]
    return r.section("⛓", "Tool-call log",
                     r.table(["tool", "status", "args (redacted)", "result"], rows),
                     lead="Every tool call from the captured runs — proposal hash at the gate, status at execute.")


def render_filled(data, root, stop):
    inv = data.get("invariant", {})
    gate = data.get("gate", {})
    verdict = r.pill("ALL LAYERS GREEN", "good") if gate.get("passed") else r.pill("REGRESSION", "bad")

    cards = ""
    for i, (layer, v) in enumerate(inv.items(), 1):
        breaches = v.get("breaches", 0)
        badge = r.pill(f"{breaches} breach", "bad") if breaches else r.pill("0 breaches", "good")
        cards += r.section(
            i, layer,
            r.card(f"{badge} &nbsp; {v.get('total', 0)} checks · {v.get('xfail', 0)} documented xfail"
                   f"<p style='margin:8px 0 0'>{r.esc(_WHY.get(layer, 'a tested control invariant.'))}</p>"
                   f"{_rows_detail(v)}"),
            lead="Drill-down: the layer's real rows — breaches (defects) and documented residuals (xfail).",
        )

    body = (
        r.section("✓", "Verdict", r.card(f"{verdict} &nbsp; {gate.get('invariant_breaches', '?')} total breaches "
                  f"across {len(inv)} control layers."),
                  lead="Every layer's verdict is computed from the eval report + the layer's real checks.")
        + cards
        + _tool_call_log(data)
    )
    return r.document(stop["title"], f"showcase · stop {stop['num']:02d}", stop["title"],
                      "Each control layer: what it proves, drilled down to its real rows.", body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

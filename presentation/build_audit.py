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


def render_filled(data, root, stop):
    inv = data.get("invariant", {})
    gate = data.get("gate", {})
    verdict = r.pill("ALL LAYERS GREEN", "good") if gate.get("passed") else r.pill("REGRESSION", "bad")

    cards = ""
    for i, (layer, v) in enumerate(inv.items(), 1):
        breaches = v.get("breaches", 0)
        badge = r.pill(f"{breaches} breach", "bad") if breaches else r.pill("0 breaches", "good")
        residuals = "".join(
            f"<li><span class=k>xfail:</span> {r.esc(x.get('attack_class',''))} — {r.esc(x.get('residual',''))}</li>"
            for x in v.get("xfail_rows", [])
        )
        res_html = f"<ul>{residuals}</ul>" if residuals else ""
        cards += r.section(
            i, layer,
            r.card(f"{badge} &nbsp; {v.get('total',0)} checks<p style='margin:8px 0 0'>"
                   f"{r.esc(_WHY.get(layer, 'a tested control invariant.'))}</p>{res_html}"),
        )

    body = (
        r.section("✓", "Verdict", r.card(f"{verdict} &nbsp; {gate.get('invariant_breaches','?')} total breaches "
                  f"across {len(inv)} control layers."),
                  lead="Every layer's verdict is computed from the eval report + the layer's real checks.")
        + cards
    )
    return r.document(stop["title"], "showcase · stop 05", stop["title"],
                      "Each control layer: what it proves, and the real evidence.", body)


def build(root=_base.ROOT):
    return _base.build(KEY, render_filled, root)


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

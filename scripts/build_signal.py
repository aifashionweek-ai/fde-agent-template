"""Generate presentation/signal.html — "reading the eval + telemetry data → recommending back to
engineering." CRITICAL J-02: this agent has NO trained ML model — NO loss/accuracy/ROC/training curves.
Every number is REAL measured data: eval scores from evals_h2a.json, per-run token/latency/cost from the
captured telemetry fixtures (evals/fixtures/telemetry_runs.json), the read-vs-graph bench (mcp_vs_graph.json),
and the injection false-positive is LIVE-MEASURED from the real detector. recall@k is a SINGLE measured
value (the scorer does not sweep k) → rendered as a labeled stat, never a fabricated curve.
Self-contained (inline SVG only, no chart lib, no external links; shared design).
"""
import argparse, html, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))                              # so `agent.guards` resolves when run as a script
DATA = ROOT / "presentation" / "data"
FIX = ROOT / "evals" / "fixtures"

_CSS = """
:root{--bg:#fafafa;--card:#fff;--line:#e5e7eb;--txt:#1a1a2e;--dim:#6b7280;--acc:#4338ca;--good:#166534;
--warn:#b45309;--bad:#991b1b;--mono:'JetBrains Mono',ui-monospace,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.6 'Space Grotesk',-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 80px}
a.back{color:var(--acc);text-decoration:none;font-size:13px}
h1{font-size:23px;margin:6px 0 2px;letter-spacing:-.01em}.sub{color:var(--dim);margin:0 0 14px}
h2{font-size:15px;margin:30px 0 8px;text-transform:uppercase;letter-spacing:.05em;color:var(--acc);
border-bottom:1px solid var(--line);padding-bottom:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;font-size:13px}
.stat b{color:var(--acc);font-family:var(--mono);font-size:18px;display:block}
.stat .k{color:var(--dim);font-size:11px}
.rec{border-left:4px solid var(--acc)}.rec b{color:var(--txt)}
.sig{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.limit{border-left:4px solid var(--warn)}
.bl{font-family:var(--mono);font-size:11px}
.foot{color:var(--dim);font-size:12px;margin-top:36px;border-top:1px solid var(--line);padding-top:14px}
"""

def e(x): return html.escape(str(x))


def _bars(rows, unit, color="#4338ca", w=560, bh=22, gap=8):
    """Inline-SVG horizontal bar chart from REAL (label, value) rows. No chart lib, no external assets."""
    mx = max((v for _, v in rows), default=1) or 1
    labelw, valw = 130, 120
    barw = w - labelw - valw
    h = len(rows) * (bh + gap) + 6
    svg = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" font-family="JetBrains Mono, monospace" font-size="11">']
    for i, (lab, v) in enumerate(rows):
        y = i * (bh + gap) + 4
        bw = max(2, int(barw * v / mx))
        svg.append(f'<text x="0" y="{y+15}" fill="#6b7280">{e(lab)}</text>')
        svg.append(f'<rect x="{labelw}" y="{y}" width="{bw}" height="{bh}" rx="4" fill="{color}"/>')
        svg.append(f'<text x="{labelw+bw+6}" y="{y+15}" fill="#1a1a2e">{e(f"{v:,.0f}" if v>=100 else v)} {e(unit)}</text>')
    svg.append('</svg>')
    return "".join(svg)


def render(h2a, runs, mcp, dan_fp, benign_fp):
    cases = h2a["cases"]
    recall = [c["score"] for c in cases if c["layer"] == "retrieval_quality" and "score" in c]
    grounded = [c["score"] for c in cases if c["layer"] == "groundedness" and "score" in c]
    recall_mean = round(sum(recall) / len(recall), 2) if recall else None
    grounded_mean = round(sum(grounded) / len(grounded), 2) if grounded else None
    breaches = h2a["last_run_result"]["invariant_breaches"]
    total = h2a["counts"]["total"]

    order = ["self_reset", "cross_user", "policy_read", "injection", "mutate"]
    order = [k for k in order if k in runs] + [k for k in runs if k not in order]
    tok_rows = [(k, runs[k]["trace"]["totals"]["tokens"]) for k in order]
    lat_rows = [(k, runs[k]["trace"]["totals"]["latency_ms"]) for k in order]
    cost_rows = [(k, runs[k]["trace"]["totals"]["cost_usd"]) for k in order]
    read_tok = mcp["mcp"]["tokens"]; graph_tok = mcp["graph"]["tokens"]

    stats = "".join(f'<div class="stat"><b>{v}</b><span class="k">{e(k)}</span></div>' for k, v in [
        (f"recall@k (single k, n={len(recall)})", recall_mean),
        (f"groundedness (n={len(grounded)})", grounded_mean),
        ("invariant breaches", breaches),
        (f"H2A eval cases", total)])

    recs = [
        (f"Retrieval/reasoning is the cost-dominant path — injection run {runs['injection']['trace']['totals']['tokens']:,} tok "
         f"vs self-reset {runs['self_reset']['trace']['totals']['tokens']:,} tok; and a pure read over MCP is "
         f"{read_tok} tok vs {graph_tok:,} tok through the graph.",
         "Route reads over the MCP read tool (near-zero tokens); keep the governed graph for actions.",
         "evals/fixtures/telemetry_runs.json · mcp_vs_graph.json"),
        (f"The injection detector false-positives on names — live-measured: injection_score('Dan Lee') = {dan_fp} "
         f"(benign 'Alice Nguyen' = {benign_fp}); a person named Dan trips the \\bDAN\\b jailbreak pattern.",
         "Route fuzzy/short-token injection hits to human-confirm; don't auto-block on them.",
         "agent/guards.py injection_score (measured at render time)"),
        (f"Groundedness is {grounded_mean} and invariant breaches are {breaches} — the safety floor holds; "
         f"but recall@k is measured at a SINGLE k on {len(recall)} cases, so recall is the lever that will move first at scale.",
         "Invest eval effort in a multi-k recall sweep on a bigger corpus before claiming retrieval quality.",
         "evals/scorers/quality (single-k) · evals_h2a.json"),
    ]
    rec_html = "".join(
        f'<div class="card rec"><b>Signal:</b> {e(s)}<div style="margin-top:6px"><b>→ Tell engineering:</b> {e(r)}</div>'
        f'<div class="sig">from: {e(src)}</div></div>' for s, r, src in recs)

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Signal · data → recommendations</title>
<style>{_CSS}</style></head><body><div class="wrap">
<a class="back" href="/hub">← back to hub</a>
<h1>Signal — reading the data, recommending to engineering</h1>
<div class="sub">Every number is REAL measured data (eval scores + captured telemetry + a live detector reading).
This agent has no trained model — there are no loss/accuracy/ROC curves here, by design.</div>

<h2>1 · What the data shows</h2>
<div class="stats">{stats}</div>
<div class="card"><b>Per-run tokens</b> (captured telemetry, 5 scenarios)<br>{_bars(tok_rows, "tok")}</div>
<div class="card"><b>Per-run latency</b><br>{_bars(lat_rows, "ms", "#7c3aed")}</div>
<div class="card"><b>Per-run cost (USD)</b><br>{_bars([(k, v*1000) for k, v in cost_rows], "m$", "#166534")}
<div class="sig">bars in milli-dollars (×1000) for scale; real values ${cost_rows[0][1]:.4f}–${max(v for _,v in cost_rows):.4f}</div></div>
<div class="card"><b>MCP read tool vs governed graph</b> (same read): {read_tok} tok vs {graph_tok:,} tok — measured, not asserted.</div>

<h2>2 · What I'd tell engineering</h2>
{rec_html}

<h2>3 · Honest limits</h2>
<div class="card limit">Directional, not statistically powered: the eval set is <b>{total} cases</b>; the
telemetry distributions are <b>single captured runs</b> (n=1 per scenario), not production traffic; recall@k is
measured at one k. These point at levers and costs — they don't establish significance.</div>

<div class="foot">Generated by scripts/build_signal.py from evals_h2a.json + evals/fixtures/*.json + a live
injection_score reading — self-contained, inline SVG, no external assets. <a href="/hub" style="color:var(--acc)">← hub</a></div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "presentation" / "signal.html"))
    a = ap.parse_args()
    h2a = json.loads((DATA / "evals_h2a.json").read_text())
    runs = json.loads((FIX / "telemetry_runs.json").read_text())
    mcp = json.loads((FIX / "mcp_vs_graph.json").read_text())
    from agent.guards import injection_score                    # live-measured FP (real detector behavior)
    dan, benign = injection_score("Dan Lee"), injection_score("Alice Nguyen")
    pathlib.Path(a.out).write_text(render(h2a, runs, mcp, dan, benign))
    print(f"wrote {a.out} — recall single-k (no curve), telemetry from {len(runs)} runs, DAN FP={dan} (live)")


if __name__ == "__main__":
    main()

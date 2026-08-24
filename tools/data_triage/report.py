"""DATA-REPORT.html generator. Reads profile.json + findings.json + (optional) clean_log.json and renders
the shared presentation design (ink-blue/cool-white, Space Grotesk + JetBrains Mono font-name stack,
SELF-CONTAINED — no external asset links). Every number is read from the JSONs; nothing is hardcoded (J-02).
Three-act shape: what the data IS · what's WRONG · trust-boundary findings · what I DID · what's still RISKY.
"""
from __future__ import annotations

import html

_CSS = """
:root{--bg:#fafafa;--card:#fff;--line:#e5e7eb;--txt:#1a1a2e;--dim:#6b7280;--acc:#4338ca;--good:#166534;
--warn:#b45309;--bad:#991b1b;--mono:'JetBrains Mono',ui-monospace,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.6 'Space Grotesk',-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:24px;margin:0 0 2px;letter-spacing:-.01em}.sub{color:var(--dim);margin:0 0 22px}
h2{font-size:15px;margin:30px 0 12px;text-transform:uppercase;letter-spacing:.05em;color:var(--acc);
border-bottom:1px solid var(--line);padding-bottom:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.meta{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 6px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size:13px}
.chip b{color:var(--acc);font-family:var(--mono)}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th,td{padding:7px 9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
td.mono,.n{font-family:var(--mono)}
.bar{position:relative;background:#eef2ff;border-radius:5px;height:16px;min-width:80px;display:inline-block;width:120px;vertical-align:middle}
.bar .fill{height:100%;border-radius:5px;background:var(--acc)}
.sev{font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:6px}
.high{background:#fef2f2;color:var(--bad)}.medium{background:#fffbeb;color:var(--warn)}.low{background:#f0fdf4;color:var(--good)}
.pill{font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:6px;background:#eef2ff;color:var(--acc);font-family:var(--mono)}
.ex{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.risk{border-left:4px solid var(--warn)}.did{border-left:4px solid var(--good)}
.foot{color:var(--dim);font-size:12px;margin-top:36px;border-top:1px solid var(--line);padding-top:14px}
ul{margin:6px 0 0;padding-left:18px}li{margin:4px 0}
"""

def _e(x): return html.escape(str(x))
def _bar(pct): return f'<span class="bar"><span class="fill" style="width:{min(100,max(0,pct)):.0f}%"></span></span>'


def render(profile: dict, findings: dict, clean_log: dict | None = None) -> str:
    p, f = profile, findings
    reader_ok = p.get("reader_status") == "ok"
    # --- act 1: what it IS ---
    chips = "".join(f'<div class="chip">{k} <b>{_e(v)}</b></div>' for k, v in [
        ("format", p.get("format")), ("size", p.get("size_human")),
        ("rows", f'{p.get("rows"):,}' if isinstance(p.get("rows"), int) else p.get("rows")),
        ("cols", p.get("cols")), ("encoding", p.get("encoding")),
        ("memory", p.get("memory_strategy"))])
    if not reader_ok:
        cols_tbl = f'<div class="card risk">{_e(p.get("reader_status"))}</div>'
    else:
        rows_html = ""
        for c in p.get("columns", []):
            mixed = '<span class="pill">MIXED</span>' if c.get("mixed_type") else ""
            samp = ", ".join(_e(s)[:24] for s in c.get("samples", [])[:3])
            rows_html += (f'<tr><td>{_e(c["name"])}</td><td><span class="pill">{_e(c["dtype"])}</span>{mixed}</td>'
                          f'<td class="n">{c["null_pct"]}% {_bar(c["null_pct"])}</td>'
                          f'<td class="n">{_e(c["distinct"])}</td><td class="ex">{samp}</td></tr>')
        cols_tbl = ('<table><thead><tr><th>column</th><th>dtype</th><th>null density</th>'
                    f'<th>distinct</th><th>samples</th></tr></thead><tbody>{rows_html}</tbody></table>')

    # --- act 2: what's WRONG (ranked) ---
    issues = []
    if reader_ok:
        for c in p.get("columns", []):
            if c["null_pct"] >= 20: issues.append((c["null_pct"], f'column <b>{_e(c["name"])}</b> is {c["null_pct"]}% null'))
        if p.get("duplicate_rows"):
            approx = " (approx)" if p.get("duplicate_approximate") else ""
            issues.append((p["duplicate_rate"] * 100, f'{p["duplicate_rows"]:,} duplicate rows — {p["duplicate_rate"]*100:.1f}%{approx}'))
        for c in p.get("columns", []):
            if c.get("mixed_type"): issues.append((15, f'column <b>{_e(c["name"])}</b> has MIXED types {_e(c.get("types_seen"))}'))
        if p.get("malformed_rows"): issues.append((10, f'{p["malformed_rows"]:,} malformed rows (wrong field count)'))
        if p.get("garbage_rows"): issues.append((10, f'{p["garbage_rows"]:,} garbage rows (encoding damage)'))
    issues.sort(key=lambda x: -x[0])
    wrong = "<ul>" + "".join(f"<li>{t}</li>" for _, t in issues) + "</ul>" if issues else '<div class="card">No structural issues detected.</div>'

    # --- act 3: trust-boundary findings ---
    fr = ""
    for fd in f.get("findings", []):
        ex = ("<div class='ex'>" + " · ".join(_e(x) for x in fd.get("examples", [])) + "</div>") if fd.get("examples") else ""
        cnt = f'<td class="n">{fd["count"]:,}</td>' if isinstance(fd.get("count"), int) else '<td class="n">—</td>'
        fr += (f'<tr><td><span class="sev {fd["severity"]}">{fd["severity"].upper()}</span></td>'
               f'<td>{_e(fd["finding"])}{ex}</td>{cnt}<td>{_e(fd.get("confidence"))}</td></tr>')
    trust = (f'<table><thead><tr><th>sev</th><th>finding</th><th>count</th><th>confidence</th></tr></thead>'
             f'<tbody>{fr}</tbody></table>') if fr else '<div class="card">No trust-boundary findings.</div>'
    if f.get("truncated"): trust += f'<div class="sub">scan sampled the first {f.get("scan_cap"):,} rows.</div>'

    # --- act 4: what I DID ---
    if clean_log:
        steps = "".join(f'<tr><td>{_e(s["step"])}</td><td class="n">{s["rows_in"]:,}</td>'
                        f'<td class="n">{s["rows_out"]:,}</td><td class="n">{s["dropped"]:,}</td>'
                        f'<td class="n">{s["cells_changed"]:,}</td></tr>' for s in clean_log.get("steps", []))
        did = (f'<div class="card did"><b>{clean_log["rows_in"]:,}</b> rows in → <b>{clean_log["rows_out"]:,}</b> rows out '
               f'(recipe: {_e(", ".join(clean_log["recipe"]))}) → <span class="ex">{_e(clean_log["out_path"])}</span>'
               f'<table><thead><tr><th>step</th><th>rows in</th><th>rows out</th><th>dropped</th><th>cells changed</th></tr></thead>'
               f'<tbody>{steps}</tbody></table></div>')
    else:
        did = '<div class="card">No cleaning run (profile-only). Re-run with <span class="ex">--clean</span> to clean + log.</div>'

    # --- act 5: what's still RISKY / not done ---
    risky = []
    if not reader_ok: risky.append(_e(p.get("reader_status")))
    if p.get("duplicate_approximate"): risky.append("duplicate rate is APPROXIMATE (hash set capped on a large file)")
    if any(c.get("distinct_capped") for c in p.get("columns", [])): risky.append("some distinct counts hit the cap (shown as ≥cap)")
    if f.get("truncated"): risky.append(f'trust scan only covered the first {f.get("scan_cap"):,} rows')
    for fd in f.get("findings", []):
        if fd.get("confidence") == "heuristic": risky.append(f'{_e(fd["finding"])} — heuristic, needs human confirmation')
    if not clean_log: risky.append("data not cleaned yet — this is a profile-only pass")
    elif clean_log:
        addressed = set(clean_log.get("recipe", []))
        if f.get("findings") and "redact_pii" not in addressed: risky.append("PII present but redact_pii was NOT in the recipe")
    risk = "<ul>" + "".join(f"<li>{t}</li>" for t in risky) + "</ul>" if risky else '<div class="card">Nothing outstanding flagged.</div>'

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Data Triage · {_e(p.get('file'))}</title>
<style>{_CSS}</style></head><body><div class="wrap">
<h1>Data Triage — {_e(p.get('file'))}</h1>
<div class="sub">First-15-minutes profile of an unknown file. Every number measured from the real bytes.</div>
<div class="meta">{chips}</div>
<h2>1 · What this data IS</h2>{cols_tbl}
<h2>2 · What's WRONG (ranked)</h2><div class="card">{wrong}</div>
<h2>3 · Trust-boundary findings</h2>{trust}
<h2>4 · What I DID</h2>{did}
<h2>5 · What's still RISKY / not done</h2><div class="card risk">{risk}</div>
<div class="foot">Generated by tools/data_triage from the real profiled file — self-contained, no external assets.</div>
</div></body></html>"""

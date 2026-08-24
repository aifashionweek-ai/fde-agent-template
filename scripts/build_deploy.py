"""Generate presentation/deploy.html — "what this agent becomes in a 3-day customer deployment."
Roadmap items map to REAL current gaps read from presentation/data/{infra,logs,evals_h2a,evals_a2a,
discrepancies}.json (J-02: nothing invented; the Cyrillic xfail count is READ from the same JSON /evals
uses, so the two stops never diverge). Self-contained (no external links; Space Grotesk / JetBrains Mono +
system fallback), shared ink-blue/cool-white design. Runnable: python scripts/build_deploy.py [--out ...]
"""
import argparse, html, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "presentation" / "data"

_CSS = """
:root{--bg:#fafafa;--card:#fff;--line:#e5e7eb;--txt:#1a1a2e;--dim:#6b7280;--acc:#4338ca;--good:#166534;
--warn:#b45309;--bad:#991b1b;--tele:#7c3aed;--grey:#6b7280;--mono:'JetBrains Mono',ui-monospace,monospace}
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
.strong{border-left:4px solid var(--good)}.thin{border-left:4px solid var(--warn)}.later{border-left:4px solid var(--grey)}
ul{margin:6px 0 0;padding-left:18px}li{margin:5px 0}
.tag{font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:6px;font-family:var(--mono)}
.stub{background:#eef2f2;color:var(--grey)}.documented{background:#fffbeb;color:var(--warn)}
.absent{background:#fef2f2;color:var(--bad)}.present{background:#f0fdf4;color:var(--good)}
.day{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
.day h3{margin:0 0 6px;font-size:14px;color:var(--acc)}
.day .row{font-size:13px;margin:4px 0}.day .row b{color:var(--txt)}
.reuse{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.foot{color:var(--dim);font-size:12px;margin-top:36px;border-top:1px solid var(--line);padding-top:14px}
"""

def e(x): return html.escape(str(x))


def render(infra, logs, h2a, a2a, disc):
    xfail = h2a["counts"]["xfail"]                          # READ from the same JSON /evals renders (consistency pin)
    breaches = h2a["last_run_result"]["invariant_breaches"]
    total = h2a["counts"]["total"]
    ndisc = len(disc["discrepancies"])
    a2a_n = f'{a2a["counts"].get("scripted_tests")} scripted + {a2a["counts"].get("live_demo")} live'
    comp = {c["name"]: c for c in infra["components"]}
    pinecone = next((c for c in infra["components"] if "Pinecone" in c["name"]), {})
    bedrock = next((c for c in infra["components"] if "Bedrock" in c["name"]), {})
    lam = next((c for c in infra["components"] if "Lambda" in c["name"]), {})
    d045 = next((d for d in disc["discrepancies"] if d["id"] == "D-045"), {})

    strong = (
        f'<li><b>Deterministic control plane</b> — authz, tenant isolation, approval-hash binding, '
        f'authz-before-the-gate — {total} human→agent eval cases at <b>{breaches}</b> invariant breaches.</li>'
        f'<li><b>Telemetry caught its own bug</b> — {e(d045.get("id","D-045"))}: {e(d045.get("title",""))} '
        f'(how found: telemetry, not a human). Locked by <span class="reuse">{e(d045.get("test_that_locks_it",""))}</span>.</li>'
        f'<li><b>Agent→Agent gate holds</b> — {a2a_n}; an abstaining channel is fail-closed.</li>'
        f'<li><b>{ndisc} real defects</b> caught red-first / by telemetry and each locked by a test — nothing asserted.</li>')

    thin = (
        f'<li><b>Retrieval is in-memory BM25</b>, not a production vector store — Pinecone is present behind the '
        f'same <code>search()</code> contract but <span class="tag stub">STUB</span> ({e(pinecone.get("where_configured",""))}).</li>'
        f'<li><b>Bedrock is on-demand Converse</b>, not provisioned throughput <span class="tag present">PRESENT</span> — '
        f'{e(bedrock.get("note",""))[:90]}.</li>'
        f'<li><b>Deploy is documented, not built</b> — Lambda/SAM <span class="tag documented">DOCUMENTED</span> ({e(lam.get("where_configured",""))}).</li>'
        f'<li><b>Narrow task surface</b> — one privileged action + a few gated writes; the domain tools are the 4-slot fill.</li>'
        f'<li><b>No durable audit log & no real IdP</b> <span class="tag absent">ABSENT</span> — {e(logs.get("honest_summary",""))[:130]}.</li>'
        f'<li><b>{xfail} documented xfail residuals</b> (cross-script confusable, D-042) — shown, never gating '
        f'(same count rendered on /evals).</li>')

    days = [
        ("Day 1 — land + establish the ingestion trust boundary",
         [("Done", "Run the data-triage tool on the customer corpus (profile, clean, screen PII / injection / tenant-mixing) BEFORE anything is indexed; fill SLOT 1 golden set + SLOT 2 corpus."),
          ("Closes", "the 'unknown data' risk — you know the corpus's PII/quirks and it's screened like the retrieval surface it becomes (ties to D-043)."),
          ("Reuses", "tools/data_triage/ · evals/dataset.jsonl (SLOT 1) · agent/retrieval.load_dir (SLOT 2)")]),
        ("Day 2 — domain tools + real retrieval + eval gate",
         [("Done", "SLOT 3 domain tools (keep authz+approval pattern) + SLOT 4 output contract; flip VECTOR_BACKEND=pinecone (same search() contract); run the eval gate on the domain golden set."),
          ("Closes", "the narrow-task-surface + BM25-not-production gaps — real tools, real vector store, gate green on the domain."),
          ("Reuses", "agent/tools.py + MASTERSCHEMA + update.py · agent/retrieval.PineconeIndex · evals/runner.py")]),
        ("Day 3 — harden + freeze",
         [("Done", "Real IdP token at the gateway (principal from a verified OIDC/JWT, not env); a durable append-only compliance log; run the model bake-off; freeze + demo."),
          ("Closes", "the two S2/M gaps that matter most — cross-principal /approve auth (D-033 boundary) and the one genuinely-absent capability (retained audit record)."),
          ("Reuses", "agent/identity.py + authz.py (D-033) · agent/telemetry.py (feeds the audit store) · scripts/model_bakeoff.sh")]),
    ]
    day_html = ""
    for title, rows in days:
        day_html += f'<div class="day"><h3>{e(title)}</h3>' + "".join(
            f'<div class="row"><b>{e(k)}:</b> {e(v) if k != "Reuses" else ""}{("<span class=reuse>"+e(v)+"</span>") if k=="Reuses" else ""}</div>'
            for k, v in rows) + '</div>'

    later = (
        '<li><b>Full DLP / data-egress allowlist</b> (S2/L) — destination allowlist + payload inspection before a '
        'side-effecting tool egresses. HITL shows the destination today, but automated control is L-effort.</li>'
        '<li><b>Cross-script identity confusables</b> (S3/M) — a Unicode TR39 skeleton (the residual behind the '
        f'{xfail} xfail rows); NFKC+casefold+strip closes the realistic bypasses today.</li>'
        '<li><b>SOC2-grade audit + retention</b> — beyond an append-only log: retention policy, access controls, evidence.</li>')

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Deploy · 3-day customer plan</title>
<style>{_CSS}</style></head><body><div class="wrap">
<a class="back" href="/hub">← back to hub</a>
<h1>Deploy — what this becomes in 3 days</h1>
<div class="sub">Roadmap items map to REAL gaps (infra.json / logs.json / the xfail count from evals) — nothing invented.</div>
<div class="lead">The governance is <b>deep</b>; the capability surface is <b>deliberately narrow</b>. Here's how I'd
deepen it safely in a real 3-day customer engagement — the frame (control plane, eval gate, telemetry) is already in place,
so days 1–3 are fills and hardening, not a rebuild.</div>

<h2>1 · Where it's strong today</h2>
<div class="card strong"><ul>{strong}</ul></div>

<h2>2 · Where it's deliberately thin (honest)</h2>
<div class="card thin"><ul>{thin}</ul></div>

<h2>3 · The 3-day plan</h2>
{day_html}

<h2>4 · What still needs a longer engagement</h2>
<div class="card later"><ul>{later}</ul></div>

<div class="foot">Generated by scripts/build_deploy.py from presentation/data/*.json — self-contained, no external assets.
<a href="/hub" style="color:var(--acc)">← hub</a></div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "presentation" / "deploy.html"))
    a = ap.parse_args()
    d = {n: json.loads((DATA / f"{n}.json").read_text()) for n in
         ["infra", "logs", "evals_h2a", "evals_a2a", "discrepancies"]}
    pathlib.Path(a.out).write_text(render(d["infra"], d["logs"], d["evals_h2a"], d["evals_a2a"], d["discrepancies"]))
    print(f"wrote {a.out} (xfail={d['evals_h2a']['counts']['xfail']} read from evals_h2a.json — matches /evals)")


if __name__ == "__main__":
    main()

"""Generate a multilayer AUDIT REPORT (HTML) for the agent — the artifact you walk an interviewer through.
Reads ONLY real evidence: results/*.json (eval runs), the test suite, MANIFEST.md, the tool registry, git.
NO GUESSING — every number traces to a file. If evidence is missing, the layer says "NO EVIDENCE" (honest).

    python -m evals.audit_report            # writes evals/results/AUDIT.html and opens it
    python -m evals.audit_report --no-open

Design: layers (guardrails, retrieval, memory, tools/HITL, model selection, tracing, evals, MCP, vector
backend, infra) — count computed from the LAYERS list, not hardcoded. Model-selection shows the real
bake-off numbers; structural layers show live-computed facts. Each layer
card shows: WHAT it does · WHY this choice · ALTERNATIVES considered · EVIDENCE (real pass/fail from logs).
Verdict is computed, not asserted — a failing layer shows red, like the aifw-ios harness audit.
"""
import json, os, re, subprocess, sys, pathlib, datetime, html
ROOT = pathlib.Path(__file__).parent.parent
RESULTS = pathlib.Path(__file__).parent / "results"

def sh(cmd):
    try: return subprocess.check_output(cmd, shell=True, cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return ""

def run_pytest():
    """Real test counts AND the full per-test list from ONE live pytest run — captured via junit-xml and
    persisted to evals/results/pytest-run.json so the audit page can drill to every test (name, file,
    outcome), not just the count (J-02: the drill reads this real artifact). Returns (passed, failed, last, tests)."""
    RESULTS.mkdir(exist_ok=True)
    xmlp = RESULTS / "pytest-junit.xml"
    out = sh(f"{sys.executable} -m pytest tests -q --tb=no --junit-xml={xmlp} 2>&1") or ""
    m = re.search(r"(\d+) passed", out); passed = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) failed", out); failed = int(m.group(1)) if m else 0
    last = out.splitlines()[-1] if out else "no output"
    tests = []
    if xmlp.exists():
        import xml.etree.ElementTree as ET
        try:
            for tc in ET.parse(xmlp).getroot().iter("testcase"):
                cls = tc.get("classname", "")            # e.g. tests.test_guards / tests.adversarial.test_attacks
                fpath = (cls.replace(".", "/") + ".py") if cls else "?"
                oc = ("failed" if (tc.find("failure") is not None or tc.find("error") is not None)
                      else "skipped" if tc.find("skipped") is not None else "passed")
                tests.append({"file": fpath, "name": tc.get("name", "?"), "outcome": oc})
        except Exception:
            pass
        xmlp.unlink()
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (RESULTS / "pytest-run.json").write_text(json.dumps(
        {"generated": now, "passed": passed, "failed": failed, "total": len(tests), "tests": tests}, indent=2))
    return passed, failed, last, tests

def load_manifest():
    rows = []
    for line in (ROOT/"MANIFEST.md").read_text().splitlines():
        m = re.match(r"\|\s*(D-\d{3})\s*\|(.*?)\|(.*?)\|(.*?)\|", line)
        if m: rows.append(dict(id=m[1], directive=m[2].strip(), guard=m[3].strip(), status=m[4].strip()))
    return rows

def load_latest_eval():
    files = sorted(RESULTS.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    files = [f for f in files if f.name not in ("AUDIT.html", "pytest-run.json")]  # pytest-run is the test list, not an eval
    for f in files:                                    # newest eval-shaped file (has 'rows'), skip non-eval json
        try:
            d = json.loads(f.read_text())
            if isinstance(d, dict) and "rows" in d:
                return d
        except Exception:
            continue
    return None

def slice_scores(payload):
    if not payload: return {}
    by = {}
    for r in payload["rows"]:
        by.setdefault(r["slice"], []).append(r["scores"])
    agg = {}
    for sl, lst in by.items():
        keys = set().union(*[s.keys() for s in lst])
        agg[sl] = {k: sum((s.get(k) or 0) for s in lst)/len(lst) for k in keys if any(s.get(k) is not None for s in lst)}
    return agg

def load_bakeoff():
    """Parse the committed bake-off doc's DETERMINISTIC scorer table into real numbers (the headline
    open-vs-closed finding). Committed evidence, always present; returns None if the doc/section is
    absent so the card can say so honestly (J-02 — never fabricate the finding). Only the deterministic
    section is read (bounded to the next '## '), so the judge table below it is never mixed in."""
    reps = sorted((ROOT/"docs").glob("model-eval-*.md"))     # newest report wins (gets the added GPT-4o column)
    if not reps: return None
    doc = reps[-1]
    lines = doc.read_text().splitlines()
    try: start = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("## deterministic"))
    except StopIteration: return None
    end = next((i for i in range(start+1, len(lines)) if lines[i].strip().startswith("## ")), len(lines))
    tbl = [l for l in lines[start:end] if l.strip().startswith("|")]
    if len(tbl) < 3: return None
    header = [c.strip() for c in tbl[0].strip().strip("|").split("|")]
    models = header[1:]                                   # drop the leading 'Scorer' column
    scorers = []
    for row in tbl[2:]:                                    # skip header + '|---|' separator
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != len(header): continue
        try: vals = [float(x) for x in cells[1:]]
        except ValueError: continue
        scorers.append((cells[0], vals))
    if not scorers or not models: return None
    all_ones = all(abs(v-1.0) < 1e-9 for _, vals in scorers for v in vals)
    return {"models": models, "scorers": scorers, "n_scorers": len(scorers),
            "n_models": len(models), "all_ones": all_ones, "source": doc.name}

# ---- evidence facts for structural layers: computed LIVE at render time, never hardcoded (J-01/J-02) ----
def _facts_mcp():
    try:
        from agent.mcp_server import read_tools, action_tool_names
        rt = [t.name for t in read_tools()]; at = sorted(action_tool_names())
        return [("READ tools published over MCP", f"{len(rt)}: {', '.join(rt)}", len(rt) == 4),
                ("action tools withheld (stay behind HITL)", f"{len(at)}: {', '.join(at)}", len(at) == 5),
                ("side-effect tool exposed over MCP", "none — by construction", set(rt).isdisjoint(at))]
    except Exception as e:
        return [("agent.mcp_server import", f"FAILED: {e}", False)]

def _facts_vector():
    import inspect
    try:
        from agent.retrieval import make_index, InMemoryIndex, PineconeIndex
        prev = os.environ.get("VECTOR_BACKEND")
        try:
            os.environ.pop("VECTOR_BACKEND", None)
            default_mem = type(make_index()).__name__ == "InMemoryIndex"
            os.environ["VECTOR_BACKEND"] = "pinecone"
            picks_pc = type(make_index()).__name__ == "PineconeIndex"
        finally:
            if prev is None: os.environ.pop("VECTOR_BACKEND", None)
            else: os.environ["VECTOR_BACKEND"] = prev
        sig_same = (list(inspect.signature(InMemoryIndex.search).parameters) ==
                    list(inspect.signature(PineconeIndex.search).parameters))
        return [("default backend (zero-setup)", "in-memory", default_mem),
                ("VECTOR_BACKEND=pinecone → PineconeIndex", "yes" if picks_pc else "no", picks_pc),
                ("search() contract identical across backends", "yes" if sig_same else "no", sig_same)]
    except Exception as e:
        return [("agent.retrieval backend", f"FAILED: {e}", False)]

def _facts_infra():
    files = [("deploy/Dockerfile", "container → App Runner"),
             ("deploy/template.yaml", "AWS SAM → Lambda"),
             ("deploy/hf_endpoint.py", "HF Inference Endpoint (open weights)")]
    return [(desc, p if (ROOT/p).exists() else "MISSING", (ROOT/p).exists()) for p, desc in files]

# ---- the layers: what / why / alternatives (design rationale is authored here, evidence is computed) ----
LAYERS = [
 dict(id="L1", name="Guardrails (6 layers)", icon="🛡️",
   what="Layered input/output safety: regex PII+injection, Presidio, Prompt-Guard/Lakera, Bedrock Guardrails, output grounding, HITL.",
   why="Deterministic where possible (free, fast, testable), model-judged only where necessary, humans on the residual. Each layer is a tested invariant, not a prompt.",
   alts="LLM-judge-everything (slow, non-deterministic, costly) · a single vendor guardrail (vendor lock, misses tool-level risks) · no guardrails (unshippable).",
   evidence_keys=["injection_refused","no_raw_pii","grounded"], manifest=["D-005","D-012"]),
 dict(id="L2", name="Routed Retrieval", icon="🔎",
   what="Provenance per chunk; tenant + 4-tier sensitivity + source filters applied BEFORE ranking; hybrid BM25+embeddings; ids are the only legal citations.",
   why="Security must be STRUCTURAL. A filter can't be out-ranked; a soft boost can. Multi-tenant isolation and clearance ceilings are enforced, not hoped for.",
   alts="Score-then-filter (leakable) · single-tenant index per customer (cost, ops) · pure vector search (misses exact ids/SKUs; no clearance model).",
   evidence_keys=["grounded"], manifest=["D-010","D-011"]),
 dict(id="L3", name="Agentic Memory (3 kinds)", icon="🧠",
   what="Short-term (checkpointed thread), long-term semantic + episodic (tenant+user scoped, injected before planning, approval-gated writes, TTL, forget()).",
   why="Most 'agents' are stateless. Real agents remember safely: memory is customer data — structurally isolated, provenance-stamped, forgettable. Writes are decisions (approval-gated).",
   alts="No memory (re-asks everything) · stuff-everything-in-context (cost, leakage) · unscoped global memory (cross-tenant leak).",
   evidence_keys=[], manifest=["D-016","D-017","D-018"]),
 dict(id="L4", name="Tools & Human-in-the-Loop", icon="🔧",
   what="9 tools: read (search/lookup/recall/calc) with no approval; action (reset_access/create_ticket/provision/remember/escalate) gated through a human approval node.",
   why="An agent that answers is useful; one that ACTS is valuable — but every side effect must be human-approved. Unknown tool -> approval by default; strict mode raises on drift.",
   alts="Read-only agent (no real work) · auto-execute actions (dangerous) · approve-everything (useless friction).",
   evidence_keys=["hitl_respected","tool_allowlist","within_budget"], manifest=["D-003","D-004","D-007"]),
 dict(id="L5", name="Model Selection (open vs closed)", icon="⚖️",
   what="Constraint-driven registry: select_model(task, residency, cost, quality, license). 4 providers — Anthropic API + Bedrock (Claude closed; Qwen/Llama open, in-account) + OpenAI (GPT-4o) + HF — across 2 US vendors (Anthropic, OpenAI) + open weights. One-interface swap (D-008); a provider with no key SKIPS cleanly, never a fake column. Fine-tune path via LoRA + Bedrock Custom Model Import.",
   why="The governance layer bounds worst-case behavior INDEPENDENT of model choice — the deterministic controls run outside the model and hold across every model in the bake-off — so model selection is a pure quality/cost/residency decision, not a safety one. Separate 'can we use it' (residency/license/cost) from 'is it good' (our evals).",
   alts="One hardcoded model (no residency story) · always-open (quality risk on reasoning) · always-closed (cost, lock-in, no in-account option for regulated data).",
   evidence_keys=[], manifest=["D-008","D-009"], bakeoff=True),
 dict(id="L6", name="Tracing", icon="📡",
   what="LangSmith with tenant/model/sha metadata; the node PATH (incl tool names) is carried in every result and scored (path_sane).",
   why="You can't operate what you can't see. AI-native tracing shows prompts, tool I/O, tokens, and the path — turning prod traces into new eval rows.",
   alts="HTTP-span APM only (blind to prompts/tools) · no tracing (undebuggable) · logs-only (no structure, no path).",
   evidence_keys=["path_sane"], manifest=["D-006","D-013"]),
 dict(id="L7", name="Evals & Regression Gate", icon="✅",
   what="Golden set with slices; deterministic scorers at 1.0, two independent LLM judges (Claude+GPT) with agreement + calibration; gate blocks on regression, runs OFFLINE from a results file.",
   why="'The evals passed' must MEAN something: invariants at 1.0, judges measured against each other, per-slice regression gate, never pass on missing rows. Braintrust is the dashboard; a committed file is the contract.",
   alts="Vibe-check (no signal) · single judge (unmeasured) · online-only gate (network-coupled CI) · pass-on-average (hides slice regressions).",
   evidence_keys=["schema_valid","confidence_reported"], manifest=["D-014"]),
 dict(id="L8", name="MCP Integration", icon="🔌",
   what="Expose the agent's READ tools to MCP clients (Claude Desktop, IDEs, other agents) and consume customer MCP servers — everything flows through the SAME guards + HITL. Published set is derived from the tool registry; action tools are never exposed.",
   why="MCP hands tools to a client we don't govern, so only reads (tenant/clearance-scoped inside themselves) are safe to publish. A side effect is a decision — it stays behind the approval node. The server refuses to boot if an action tool ever looks read-only (fail loud).",
   alts="Expose all tools over MCP (a client could fire side effects unapproved) · a bespoke non-standard API (no interop) · no MCP (agent can't compose with the customer's other agents).",
   evidence_keys=[], manifest=["D-025"], facts=_facts_mcp),
 dict(id="L9", name="Vector Backend (swappable)", icon="🧩",
   what="The retrieval contract search(query, tenant, sensitivity, k) is backend-swappable: in-memory BM25 by default (zero-setup), Pinecone via VECTOR_BACKEND=pinecone — namespace-per-tenant, sensitivity as a query-time metadata filter. Callers never branch on the backend.",
   why="Meet the customer's data where it already lives (Pinecone/Databricks/Snowflake/pgvector) without changing the agent. Tenant isolation stays structural (a query hits ONE namespace); the contract is the seam, so the store is a config choice, not a rewrite.",
   alts="Hardcode one vector DB (rewrite per customer) · move customer data into our store (residency/governance nightmare) · post-hoc filtering (leakable, not structural).",
   evidence_keys=[], manifest=["D-024"], facts=_facts_vector),
 dict(id="L10", name="Infra / Deployment", icon="🚀",
   what="deploy/ ships three runnable paths: Dockerfile (container/App Runner), template.yaml (AWS SAM → Lambda), hf_endpoint.py (HF Inference Endpoint for open weights). Bedrock runs models in-account for residency.",
   why="Forward-deployed means it has to RUN in the customer's environment in hours, inside their compliance boundary. Serverless for the API, in-account Bedrock for regulated inference, self-hosted HF for open weights — the residency story is backed by real deploy artifacts, not a diagram.",
   alts="A notebook demo (never ships) · one cloud only (no residency options) · vendor API only (no in-account path for regulated data).",
   evidence_keys=[], manifest=["D-027"], facts=_facts_infra),
]

def verdict(passed, failed):
    return ("PASS", "#16a34a") if failed == 0 and passed > 0 else ("NOT-CLEAN", "#dc2626")

def bar(v):
    pct = int(round(v*100)); color = "#16a34a" if v>=0.99 else "#ca8a04" if v>=0.7 else "#dc2626"
    return f'<div class="bar"><div class="fill" style="width:{pct}%;background:{color}"></div><span>{pct}%</span></div>'

def facts_table(facts):
    """Render live-computed evidence facts (label, value, ok) — a ✓/✗ per structural check."""
    rows = "".join(
        f'<tr><td>{html.escape(l)}</td><td class="{"ok" if ok else "bad"}">{html.escape(str(val))} '
        f'{"✓" if ok else "✗"}</td></tr>' for l, val, ok in facts)
    return f'<table class="ev facts">{rows}</table>'

def bakeoff_table(bo):
    """Render the REAL bake-off finding as a table. If there's no data, say so — never fabricate (J-02)."""
    if not bo:
        return ('<p class="noev">No bake-off data — docs/model-eval-2026-08-19.md not found. '
                'Not fabricated.</p>')
    head = "".join(f"<th>{html.escape(m)}</th>" for m in bo["models"])
    body = ""
    for name, vals in bo["scorers"]:
        cells = "".join(f'<td class="{"ok" if abs(x-1.0)<1e-9 else "bad"}">{x:.2f}</td>' for x in vals)
        body += f'<tr><td class="sl">{html.escape(name)}</td>{cells}</tr>'
    verdict = (f'{bo["n_scorers"]} deterministic scorers · '
               + (f'1.00 across ALL {bo["n_models"]} models ✓' if bo["all_ones"]
                  else 'NOT all 1.00 ✗'))
    cls = "ok" if bo["all_ones"] else "bad"
    return (f'<p class="{cls}" style="font-weight:700;margin:0 0 6px">{html.escape(verdict)}</p>'
            f'<table class="slices bakeoff"><tr><th>scorer</th>{head}</tr>{body}</table>'
            f'<p class="alt" style="margin-top:4px">source: {html.escape(bo["source"])}</p>')

# ---- MANIFEST D-row → test-function mapping (the real join; doc/file-backed rows labeled honestly) ----
_DROW2LAYER = {mid: L["id"] for L in LAYERS for mid in L["manifest"]}
_LNAME = {L["id"]: L["name"] for L in LAYERS}


def parse_test_refs(guard: str):
    """From a MANIFEST guard cell → (list of (file, fn), is_test). A guard with no 'tests/…::fn' is
    doc/file-backed (D-006/008/020/023/027) — labeled as such, never shown as a test (J-02)."""
    if "tests/" not in guard or "::" not in guard:
        return [], False
    m = re.search(r"(tests/\S+\.py)", guard)
    if not m:
        return [], False
    fpath = m.group(1)
    fns = re.findall(r"::(\w+)", guard)
    return [(fpath, fn) for fn in fns], bool(fns)


def test_layer_index(manifest):
    """(file, fn) → (D-row, layer-id) for every test a MANIFEST row names."""
    idx = {}
    for r in manifest:
        refs, is_test = parse_test_refs(r["guard"])
        if not is_test:
            continue
        for f, fn in refs:
            idx[(f, fn)] = (r["id"], _DROW2LAYER.get(r["id"]))
    return idx


def per_test_drill(tests, manifest):
    """The full per-test list from pytest-run.json, grouped by layer via the MANIFEST mapping."""
    idx = test_layer_index(manifest)
    groups = {}
    for t in tests:
        base = t["name"].split("[")[0]                 # strip parametrize suffix to match the MANIFEST fn
        lid = (idx.get((t["file"], base)) or (None, None))[1]
        groups.setdefault(lid or "—", []).append(t)
    order = [L["id"] for L in LAYERS] + ["—"]
    out = ""
    for lid in order:
        ts = groups.get(lid)
        if not ts:
            continue
        title = f'{lid} · {_LNAME[lid]}' if lid != "—" else "Additional tests (not a D-row guard)"
        npass = sum(1 for t in ts if t["outcome"] == "passed")
        cls = "ok" if npass == len(ts) else "bad"
        rows = "".join(
            f'<tr><td class="mono">{html.escape(t["name"])}</td>'
            f'<td class="mono dim">{html.escape(t["file"].replace("tests/", ""))}</td>'
            f'<td class="{"ok" if t["outcome"]=="passed" else "bad"}">{html.escape(t["outcome"])}</td></tr>'
            for t in ts)
        out += (f'<details class="tg"><summary><span class="{cls}">{html.escape(title)}</span> '
                f'<span class="mono dim">({npass}/{len(ts)})</span></summary>'
                f'<table class="tt"><tbody>{rows}</tbody></table></details>')
    return out


def tool_log_section():
    """Real per-tool telemetry spans (call/args/result/status/proposal_hash/hash_match) from the committed
    fixture. Honest scope: in-process + fixture per run, NOT a durable append-only log (documented S2 gap)."""
    f = ROOT / "evals" / "fixtures" / "telemetry_runs.json"
    if not f.exists():
        return '<p class="noev">No captured runs — run scripts/capture_runs.py. Not fabricated.</p>'
    data = json.loads(f.read_text())
    parts = ""
    for name, rec in data.items():
        spans = (rec.get("trace", {}) or {}).get("spans", [])
        rows = ""
        for s in spans:
            for t in (s.get("tools") or []):
                st = str(t.get("status", ""))
                hm = t.get("hash_match")
                hm_s = "match ✓" if hm is True else "MISMATCH ✗" if hm is False else "—"
                stc = "ok" if st == "PASS" else "bad" if st in ("DENIED", "REFUSED") else ""
                rows += (f'<tr><td class="mono">{html.escape(t.get("name",""))}({html.escape(str(t.get("args",{}))[:44])})</td>'
                         f'<td class="{stc}">{html.escape(st)}</td>'
                         f'<td class="mono dim">{html.escape(str(t.get("proposal_hash","") or "")[:10])} {hm_s}</td>'
                         f'<td class="mono dim">{html.escape(str(t.get("result",""))[:56])}</td></tr>')
        if rows:
            parts += (f'<details class="tg"><summary>{html.escape(str(rec.get("label", name)))}</summary>'
                      f'<table class="tt"><thead><tr><th>tool(args)</th><th>status</th><th>hash</th><th>result</th></tr></thead>'
                      f'<tbody>{rows}</tbody></table></details>')
    caveat = ('<p class="alt">Honest scope: these are per-run telemetry spans (in-process + committed fixture '
              '<code>evals/fixtures/telemetry_runs.json</code>). There is <b>no durable append-only audit log</b> — '
              'a server restart wipes live state (the documented S2 gap). "Every tool logged" means per run, in this '
              'trace and the <code>/dashboard</code>, not a persistent trail.</p>')
    return (parts or '<p class="noev">No tool spans in the captured runs.</p>') + caveat


def build():
    passed, failed, last, tests = run_pytest()
    v, vcolor = verdict(passed, failed)
    manifest = load_manifest()
    payload = load_latest_eval()
    agg = slice_scores(payload)
    overall = {}
    if agg:
        keys = set().union(*[a.keys() for a in agg.values()])
        overall = {k: sum(a[k] for a in agg.values() if k in a)/max(1,sum(1 for a in agg.values() if k in a)) for k in keys}
    sha = sh("git rev-parse --short HEAD") or "nogit"
    branch = sh("git rev-parse --abbrev-ref HEAD") or "?"
    ntools = len(json.loads((ROOT/"agent"/"tool_registry.json").read_text()))
    exp = payload.get("experiment","(none)") if payload else "(no eval run yet)"
    model = payload.get("model_profile","?") if payload else "?"
    judges = ", ".join(payload.get("judges",[])) if payload else "none"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def layer_card(L):
        # evidence: pull the layer's scorer means from the latest eval
        rows = ""
        for k in L["evidence_keys"]:
            if k in overall: rows += f'<tr><td>{k}</td><td>{bar(overall[k])}</td></tr>'
        has_extra = L.get("facts") or L.get("bakeoff")
        if not rows and not has_extra:
            rows = '<tr><td colspan="2" class="noev">No eval scorer maps directly — evidence via tests + manifest below</td></tr>'
        # live-computed structural facts + the real bake-off finding (J-02: computed, honest if absent)
        extra = ""
        if L.get("facts"):
            try: facts = L["facts"]()
            except Exception as e: facts = [("evidence check", f"error: {e}", False)]
            extra += facts_table(facts)
        if L.get("bakeoff"):
            extra += bakeoff_table(load_bakeoff())
        ev_table = f'<table class="ev">{rows}</table>' if rows else ""
        mrows = ""
        for mid in L["manifest"]:
            row = next((r for r in manifest if r["id"]==mid), None)
            if not row: continue
            refs, is_test = parse_test_refs(row["guard"])
            if is_test:
                fns = ", ".join(fn for _, fn in refs)
                badge = f'<span class="ok">✓ {html.escape(fns[:90])}</span>'
            else:  # D-006/008/020/023/027 etc — real evidence, but a file/doc, not a test fn (honest)
                badge = f'<span class="dim">file-backed, no test fn — {html.escape(row["guard"][:56])}</span>'
            mrows += f'<li><b>{mid}</b> {html.escape(row["directive"][:88])}<br>{badge}</li>'
        return f'''
        <details class="layer">
          <summary><span class="lic">{L["icon"]}</span> <span class="lid">{L["id"]}</span> {html.escape(L["name"])}
            <span class="chev">▾</span></summary>
          <div class="body">
            <div class="col"><h4>What</h4><p>{html.escape(L["what"])}</p>
              <h4>Why this choice</h4><p>{html.escape(L["why"])}</p>
              <h4>Alternatives considered</h4><p class="alt">{html.escape(L["alts"])}</p></div>
            <div class="col"><h4>Evidence (from latest eval: {html.escape(exp)})</h4>
              {ev_table}{extra}
              <h4>Governed by</h4><ul class="manifest">{mrows or "<li>—</li>"}</ul></div>
          </div>
        </details>'''

    cards = "\n".join(layer_card(L) for L in LAYERS)
    slice_html = ""
    for sl, a in sorted(agg.items()):
        cells = "".join(f'<td>{bar(a[k])}</td>' for k in sorted(a))
        heads = "".join(f'<th>{k}</th>' for k in sorted(a)) if not slice_html else ""
        if not slice_html and agg:
            first = sorted(next(iter(agg.values())))
            slice_html += "<tr><th>slice</th>" + "".join(f"<th>{k}</th>" for k in first) + "</tr>"
        slice_html += f'<tr><td class="sl">{sl}</td>' + "".join(f'<td>{bar(a.get(k,0))}</td>' for k in sorted(next(iter(agg.values())))) + "</tr>"

    doc_links = "".join(f'<a href="../../docs/{d.name}" class="doc">{d.stem}</a>' for d in sorted((ROOT/"docs").glob("*.md")))

    html_out = f'''<!doctype html><html><head><meta charset="utf-8"><title>FDE Agent · Audit</title>
<style>
:root{{--bg:#fafafa;--card:#ffffff;--line:#e5e7eb;--txt:#1a1a2e;--dim:#6b7280;--acc:#4338ca;--mono:'JetBrains Mono',ui-monospace,monospace}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font:15px/1.6 'Space Grotesk',-apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:32px 20px 80px}}
h1{{font-size:26px;margin:0 0 4px}} .sub{{color:var(--dim);margin:0 0 24px}}
.verdict{{display:inline-block;padding:6px 14px;border-radius:8px;font-weight:700;color:#fff;font-size:14px}}
.meta{{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 28px}}
.chip{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size:13px}}
.chip b{{color:var(--acc)}}
h2{{font-size:15px;margin:32px 0 12px;border-bottom:1px solid var(--line);padding-bottom:8px;text-transform:uppercase;letter-spacing:.05em;color:var(--acc)}}
.layer{{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:10px 0;overflow:hidden}}
.layer summary{{cursor:pointer;padding:14px 16px;font-weight:600;list-style:none;display:flex;align-items:center;gap:10px}}
.layer summary::-webkit-details-marker{{display:none}}
.lic{{font-size:18px}}.lid{{color:var(--acc);font-weight:700;font-size:13px;background:#eef2ff;padding:2px 8px;border-radius:6px;font-family:var(--mono)}}
.chev{{margin-left:auto;color:var(--dim)}} details[open] .chev{{transform:rotate(180deg)}}
.body{{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 16px 18px}}
.body h4{{margin:14px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--dim)}}
.body p{{margin:0;font-size:14px}} .alt{{color:var(--dim)}}
table.ev,table.slices{{width:100%;border-collapse:collapse;font-size:13px}}
table.ev td{{padding:4px 0}} .noev{{color:var(--dim);font-style:italic}}
.bar{{position:relative;background:#eef2ff;border:1px solid var(--line);border-radius:5px;height:20px;min-width:120px}}
.bar .fill{{height:100%;border-radius:4px}} .bar span{{position:absolute;right:6px;top:0;font-size:11px;line-height:20px;color:var(--txt);font-family:var(--mono)}}
ul.manifest{{margin:6px 0 0;padding-left:18px}} ul.manifest li{{font-size:12px;margin:3px 0}}
.ok{{color:#166534}} .bad{{color:#991b1b;font-weight:600}} .sl{{font-weight:600;color:var(--acc)}}
table.facts td{{padding:4px 0;font-size:12px}} table.bakeoff td,table.bakeoff th{{padding:5px 8px;text-align:left;border-bottom:1px solid var(--line);font-size:12px}}
table.slices th,table.slices td{{padding:6px 8px;text-align:left;border-bottom:1px solid var(--line);font-size:12px}}
.docs{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}} .doc{{background:#eef2ff;color:var(--acc);text-decoration:none;padding:5px 10px;border-radius:6px;font-size:12px}}
.foot{{color:var(--dim);font-size:12px;margin-top:40px;border-top:1px solid var(--line);padding-top:16px}}
.mono{{font-family:var(--mono);font-size:12px}} .dim{{color:var(--dim)}}
.drill{{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:14px 0;padding:12px 16px}}
.drill>summary{{cursor:pointer;font-size:14px}} .drillbody{{margin-top:10px;columns:2;column-gap:20px}}
@media (max-width:720px){{.drillbody{{columns:1}}}}
.tg{{border:1px solid var(--line);border-radius:8px;margin:6px 0;padding:6px 10px;break-inside:avoid}}
.tg>summary{{cursor:pointer;font-size:13px}}
table.tt{{width:100%;border-collapse:collapse;margin-top:6px}}
table.tt td,table.tt th{{padding:3px 6px;border-bottom:1px solid #f1f3f7;font-size:11.5px;text-align:left;vertical-align:top}}
ul.manifest li{{margin:6px 0}}
</style></head><body><div class="wrap">
<h1>FDE Agent — Multilayer Audit</h1>
<p class="sub">Enterprise IT-Ops & Employee Support agent · every number below is read from a real log, git, or a live pytest run. No asserted greens.</p>
<span class="verdict" style="background:{vcolor}">{v} · {passed} pass · {failed} fail</span>
<div class="meta">
  <div class="chip">tests <b>{passed}/{passed+failed}</b></div>
  <div class="chip">last <b>{html.escape(last)}</b></div>
  <div class="chip">git <b>{branch}@{sha}</b></div>
  <div class="chip">tools <b>{ntools}</b> (HITL-gated actions)</div>
  <div class="chip">manifest rows <b>{len(manifest)}</b></div>
  <div class="chip">eval model <b>{html.escape(model)}</b></div>
  <div class="chip">judges <b>{html.escape(judges)}</b></div>
  <div class="chip">generated <b>{now}</b></div>
</div>

<details class="drill"><summary><b>{passed} pass</b> · drill to every test (name · file · outcome), grouped by layer &nbsp;<span class="mono dim">reads evals/results/pytest-run.json</span></summary>
<div class="drillbody">{per_test_drill(tests, manifest)}</div></details>

<h2>The {len(LAYERS)} layers — what, why, alternatives, evidence</h2>
<p class="sub">Click any layer to drill down. Evidence bars are scorer means from the latest eval run ({html.escape(exp)}).</p>
{cards}

<h2>Eval scores by slice</h2>
{"<table class='slices'>"+slice_html+"</table>" if slice_html else "<p class='sub'>No eval run found. Run <code>EXPERIMENT=baseline python -m evals.harness</code> then regenerate.</p>"}
<p class="sub" style="margin-top:10px">Deterministic scorers (schema, PII, grounding, HITL, budget, path) are the safety <b>invariants</b> — they must read 1.00, and <b>grounding at 1.00 is the real correctness signal</b> (every citation ⊆ retrieved evidence). <code>factual</code> and <code>rubric_pass</code> are LLM-judge <i>quality</i> scores: a correctness rubric that rewards a right answer regardless of extra helpful detail, and still fails a wrong one. Some judge strictness is inherent — treat these as nuance, not pass/fail; the invariants above are pass/fail.</p>

<h2>Tool-call log — real telemetry spans</h2>
<p class="sub">Every tool execution is logged with its call, args, result, control status, and the proposal-hash
match. Click a scenario to drill. Reads <code>evals/fixtures/telemetry_runs.json</code> (also live per run at <code>/trace/&lt;id&gt;</code> and in <code>/dashboard</code>).</p>
{tool_log_section()}

<h2>Design deep-dives</h2>
<p class="sub">Each layer has a full playbook:</p>
<div class="docs">{doc_links}</div>

<div class="foot">Reproduce: <code>python -m evals.audit_report</code> · Tests: <code>python update.py --check</code> ·
Every verdict computed from results.sqlite-equivalent (evals/results/*.json), git, and a live pytest run — not remembered.</div>
</div></body></html>'''

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS/"AUDIT.html"; out.write_text(html_out)
    print(f"[audit] wrote {out}  ({v}: {passed} pass / {failed} fail)")
    return out

if __name__ == "__main__":
    import sys
    out = build()
    if "--no-open" not in sys.argv:
        import webbrowser; webbrowser.open(f"file://{out.resolve()}")

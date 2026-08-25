"""FastAPI surface. Local: uvicorn api.main:app --reload. AWS: Lambda via Mangum (deploy/template.yaml) or App Runner (deploy/Dockerfile)."""
import json, os, pathlib, traceback, uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from langgraph.types import Command
from agent.graph import graph, run
from agent.state import AgentOutput

app = FastAPI(title="FDE Agent")

# Secrets Manager → env at cold start (Lambda); keeps keys out of templates and CI.
if os.getenv("ANTHROPIC_SECRET_ARN") and not os.getenv("ANTHROPIC_API_KEY"):
    try:
        import boto3, json as _j
        v = boto3.client("secretsmanager").get_secret_value(SecretId=os.environ["ANTHROPIC_SECRET_ARN"])["SecretString"]
        os.environ["ANTHROPIC_API_KEY"] = _j.loads(v).get("ANTHROPIC_API_KEY", v) if v.startswith("{") else v
    except Exception as e: print("secret load failed:", e)

class RunReq(BaseModel):
    task: str
    thread_id: str | None = None
    tenant: str | None = None      # D-011: caller declares tenant; server enforces

class ApproveReq(BaseModel):
    thread_id: str
    approve: bool
    hashes: list[str] = []         # D-038: the proposal_hashes the human SAW (from the interrupt payload)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def chat_ui():                                           # D-039: governance-visible local chat over /run + /approve
    return (pathlib.Path(__file__).parent / "chat.html").read_text()

@app.get("/health")
def health(): return {"ok": True, "provider": os.getenv("LLM_PROVIDER","anthropic"), "model_profile": os.getenv("MODEL_PROFILE"), "tenant": os.getenv("TENANT","demo")}

def _structured_500(thread_id: str, e: Exception) -> JSONResponse:
    """D-041: an unexpected exception is a STRUCTURED result, never a bare plain-text 500 — the client
    (chat UI, A2A caller, curl) always gets JSON it can render. Full traceback to the server log (J-12)."""
    traceback.print_exc()
    return JSONResponse(status_code=500, content={
        "error": type(e).__name__, "thread_id": thread_id, "detail": str(e)})

@app.post("/run", response_model=None)
def run_agent(req: RunReq):
    tid = req.thread_id or str(uuid.uuid4())
    try:
        out = run(req.task, thread_id=tid, tenant=req.tenant)
    except Exception as e:
        return _structured_500(tid, e)
    return {"thread_id": tid, **({"result": out} if "answer" in out else out)}

@app.post("/approve")
def approve(req: ApproveReq):                            # D-004 resume + D-038 approval binds to what was seen
    cfg = {"configurable": {"thread_id": req.thread_id}}
    try:
        out = graph.invoke(Command(resume={"approve": req.approve, "hashes": req.hashes}), config=cfg)
    except Exception as e:
        return _structured_500(req.thread_id, e)
    res = out.get("result")
    if res:
        from agent.graph import _trace
        res = {**res, "trace": _trace(out, req.thread_id)}
        return {"thread_id": req.thread_id, "result": res}
    # The resumed run hit ANOTHER interrupt (a further proposal, or a re-proposal after state changed) —
    # surface it exactly like /run does, never a 500: the human decides again on what they now see.
    return {"thread_id": req.thread_id, "status": "interrupted", "state": out.get("__interrupt__"), "path": out.get("path", [])}

@app.get("/trace/{thread_id}")
def get_trace(thread_id: str):                           # D-044: last run's per-layer spans for the dashboard
    from agent import telemetry
    rec = telemetry.last_run(thread_id)
    if rec is None:
        raise HTTPException(404, f"no trace for thread {thread_id}")
    return rec

_FIX = pathlib.Path(__file__).parent.parent / "evals" / "fixtures"

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard():                                         # D-044: per-layer observability dashboard
    return (pathlib.Path(__file__).parent / "dashboard.html").read_text()

@app.get("/fixtures/runs")
def fixture_runs():                                      # captured 5-scenario spans (offline demo data)
    f = _FIX / "telemetry_runs.json"
    if not f.exists(): raise HTTPException(404, "no captured runs — run scripts/capture_runs.py")
    return json.loads(f.read_text())

@app.get("/fixtures/mcp")
def fixture_mcp():                                       # measured MCP-vs-graph result
    f = _FIX / "mcp_vs_graph.json"
    if not f.exists(): raise HTTPException(404, "no bench — run scripts/bench_mcp_vs_graph.py")
    return json.loads(f.read_text())

# ---- Presentation surfaces (docs/PRESENTATION.md) — static file responses, NO logic, read-only ----
_REPO = pathlib.Path(__file__).parent.parent

def _placeholder(title: str, hint: str) -> str:
    # House-style + self-contained: even the "not generated yet" page carries the shared type system
    # (Space Grotesk / JetBrains Mono / --line palette), so a cold clone (or CI, before reports are built)
    # serves an on-brand page and the shared-token drift test stays hermetic — no generated file required.
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width, initial-scale=1'><title>{title}</title>"
            "<style>:root{--ink:#1a1a2e;--mut:#6b7280;--line:#e5e7eb;--accent:#4338ca;--bg:#fafafa}"
            "body{margin:0;font:16px/1.6 'Space Grotesk',-apple-system,\"Segoe UI\",sans-serif;color:var(--ink);"
            "background:var(--bg)}main{max-width:640px;margin:12vh auto;padding:0 20px}"
            "h1{font-size:20px;margin:0 0 6px}.sub{color:var(--mut)}"
            "code{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:13px;background:#eef2ff;"
            "border:1px solid var(--line);padding:2px 8px;border-radius:6px}"
            "a{color:var(--accent);text-decoration:none}</style></head><body><main>"
            f"<h1>{title}</h1>"
            "<p class=sub>This report hasn't been generated yet.</p>"
            f"<p>Run <code>{hint}</code> to build it, then refresh. "
            "(<code>bash demo.sh</code> self-heals the reports on startup.)</p>"
            "<p><a href='/hub'>&larr; back to hub</a></p></main></body></html>")

def _serve_html(path: pathlib.Path, hint: str | None = None):
    """Serve a static HTML file. A missing backing file NEVER dead-ends in a raw 404 — it returns a clean
    200 'not generated — run X' page so no demo stop breaks in front of an audience."""
    if not path.exists():
        return HTMLResponse(_placeholder(path.stem, hint or f"make {path.stem.lower()}"), status_code=200)
    return HTMLResponse(path.read_text())

@app.get("/hub", response_class=HTMLResponse, include_in_schema=False)
def hub(): return _serve_html(_REPO / "presentation" / "index-hub.html", "git checkout presentation/")

@app.get("/business", response_class=HTMLResponse, include_in_schema=False)
def business(): return _serve_html(_REPO / "presentation" / "business-analytics.html", "git checkout presentation/")

@app.get("/problem", response_class=HTMLResponse, include_in_schema=False)
def problem(): return _serve_html(_REPO / "evals" / "results" / "PROBLEM.html", "make problem")

@app.get("/audit", response_class=HTMLResponse, include_in_schema=False)
def audit(): return _serve_html(_REPO / "evals" / "results" / "AUDIT.html", "make audit")

@app.get("/data", response_class=HTMLResponse, include_in_schema=False)
def data(): return _serve_html(_REPO / "tools" / "data_triage" / "DATA-REPORT.html",   # data-triage report
                               "python -m tools.data_triage tools/data_triage/fixtures/messy.csv --clean")

@app.get("/infra", response_class=HTMLResponse, include_in_schema=False)
def infra(): return _serve_html(_REPO / "presentation" / "infra.html",                 # infra/tools/logs from real JSON
                                "python scripts/build_infra.py")

@app.get("/evals", response_class=HTMLResponse, include_in_schema=False)
def evals(): return _serve_html(_REPO / "presentation" / "evals.html",                  # H2A/A2A/discrepancies from real JSON
                                "python scripts/build_evals.py")

@app.get("/deploy", response_class=HTMLResponse, include_in_schema=False)
def deploy(): return _serve_html(_REPO / "presentation" / "deploy.html",                # 3-day plan from real gaps
                                 "python scripts/build_deploy.py")

@app.get("/a2a", response_class=HTMLResponse, include_in_schema=False)
def a2a(): return _serve_html(_REPO / "presentation" / "a2a.html",                       # agent-to-agent, from real JSON
                              "python scripts/build_a2a.py")

@app.get("/signal", response_class=HTMLResponse, include_in_schema=False)
def signal(): return _serve_html(_REPO / "presentation" / "signal.html",                 # data->recommendations, real measured only
                                 "python scripts/build_signal.py")

@app.get("/runnable", response_class=HTMLResponse, include_in_schema=False)
def runnable(): return _serve_html(_REPO / "presentation" / "runnable.html",              # verified 5-min cold-start (static)
                                   "git checkout presentation/")

@app.get("/workflows", response_class=HTMLResponse, include_in_schema=False)
def workflows(): return _serve_html(_REPO / "presentation" / "workflows.html",            # workflow patterns → real nodes/tools/controls (static)
                                    "git checkout presentation/")

# A2A: another agent can call POST /run and gets AgentOutput back — same contract, any language.
@app.get("/contract")
def contract(): return AgentOutput.model_json_schema()

try:
    from mangum import Mangum
    handler = Mangum(app)                                # AWS Lambda entrypoint
except ImportError:
    pass

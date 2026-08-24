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


# A2A: another agent can call POST /run and gets AgentOutput back — same contract, any language.
@app.get("/contract")
def contract(): return AgentOutput.model_json_schema()

try:
    from mangum import Mangum
    handler = Mangum(app)                                # AWS Lambda entrypoint
except ImportError:
    pass

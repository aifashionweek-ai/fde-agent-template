"""FastAPI surface. Local: uvicorn api.main:app --reload. AWS: Lambda via Mangum (deploy/template.yaml) or App Runner (deploy/Dockerfile)."""
import os, uuid
from fastapi import FastAPI, HTTPException
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

@app.get("/health")
def health(): return {"ok": True, "provider": os.getenv("LLM_PROVIDER","anthropic"), "model_profile": os.getenv("MODEL_PROFILE"), "tenant": os.getenv("TENANT","demo")}

@app.post("/run", response_model=None)
def run_agent(req: RunReq):
    tid = req.thread_id or str(uuid.uuid4())
    out = run(req.task, thread_id=tid, tenant=req.tenant)
    return {"thread_id": tid, **({"result": out} if "answer" in out else out)}

@app.post("/approve")
def approve(req: ApproveReq):                            # D-004 resume after human decision
    cfg = {"configurable": {"thread_id": req.thread_id}}
    out = graph.invoke(Command(resume=req.approve), config=cfg)
    if not out.get("result"): raise HTTPException(500, "no result after resume")
    return {"thread_id": req.thread_id, "result": out["result"]}

# A2A: another agent can call POST /run and gets AgentOutput back — same contract, any language.
@app.get("/contract")
def contract(): return AgentOutput.model_json_schema()

try:
    from mangum import Mangum
    handler = Mangum(app)                                # AWS Lambda entrypoint
except ImportError:
    pass

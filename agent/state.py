from typing import Annotated, Optional
from pydantic import BaseModel, Field, field_validator
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
import json, pathlib

ALLOWED_TOOLS = {t["name"] for t in json.loads((pathlib.Path(__file__).parent/"tool_registry.json").read_text())}

class Action(BaseModel):
    tool: str
    args: dict = {}
    @field_validator("tool")
    @classmethod
    def in_allowlist(cls, v):
        if v not in ALLOWED_TOOLS: raise ValueError(f"tool '{v}' not in allowlist")  # D-003
        return v

class AgentOutput(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[str] = []
    actions: list[Action] = []

class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    task: str
    plan: list[str]
    step_count: int
    tool_calls: int
    result: Optional[dict]
    needs_approval: bool
    errors: list[str]
    path: list[str]              # node sequence, D-013 (trace path)
    principal: Optional[dict]    # who is calling (identity.Principal.as_claims()); authz uses it, D-033

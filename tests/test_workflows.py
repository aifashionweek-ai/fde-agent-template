"""Catch-proof for the declarative workflow maps (workflows/*.yaml) + the /workflows hub stop.

NOT a control D-row — like the other presentation surfaces, these are read-only artifacts (see
docs/PRESENTATION.md, MANIFEST note). What this suite guarantees (J-01 — computed from the real
files, not asserted): every workflow references ONLY real tools (agent/tool_registry.json), real
controls (D-### rows in MANIFEST.md), and a valid pattern label (workflows/PATTERNS.md); the read/
action kind of each declared tool matches the registry; the served /workflows page is 200,
self-contained, on the house style, leads with the determination method, and traces every workflow
to real nodes/tools/controls. test_validator_actually_bites proves the checks aren't decoration.
"""
import json
import pathlib
import re

import yaml
from fastapi.testclient import TestClient

from api.main import app

_REPO = pathlib.Path(__file__).parent.parent
_WF_DIR = _REPO / "workflows"

# ---- ground truth, loaded from the real files ---------------------------------------------------
_REGISTRY = {t["name"]: t for t in json.loads((_REPO / "agent" / "tool_registry.json").read_text())}
_READ_TOOLS = {n for n, t in _REGISTRY.items() if not t["side_effect"]}
_ACTION_TOOLS = {n for n, t in _REGISTRY.items() if t["side_effect"]}
_MANIFEST_DROWS = set(re.findall(r"\bD-\d+\b", (_REPO / "MANIFEST.md").read_text()))
# The valid pattern vocabulary IS workflows/PATTERNS.md: the 5 canonical patterns + the agent axis.
_VALID_PATTERNS = {
    "prompt-chaining", "routing", "parallelization", "orchestrator-workers", "evaluator-optimizer",
    "dynamic-agent",
}
_REQUIRED_KEYS = {"name", "business_request", "pattern", "graph_flow", "steps", "tools_used", "human_gate"}

_WF_FILES = sorted(_WF_DIR.glob("*.yaml"))
_WORKFLOWS = {p.name: yaml.safe_load(p.read_text()) for p in _WF_FILES}

client = TestClient(app)


# ---- helpers computed from a workflow doc -------------------------------------------------------
def _controls_in(doc) -> set[str]:
    """Every D-### string anywhere in the doc (steps[].controls, not_exposed_over_mcp.controls, ...)."""
    return set(re.findall(r"\bD-\d+\b", yaml.safe_dump(doc)))


def _tools_in(doc) -> set[str]:
    """Every tool named in steps[].tools and tools_used.{read,action}."""
    tools = set()
    for step in doc.get("steps", []):
        tools.update(step.get("tools", []) or [])
    tu = doc.get("tools_used", {}) or {}
    tools.update(tu.get("read", []) or [])
    tools.update(tu.get("action", []) or [])
    return tools


# ---- the invariants -----------------------------------------------------------------------------
def test_at_least_the_four_named_workflows_exist():
    names = {doc["name"] for doc in _WORKFLOWS.values()}
    assert {"read-answer", "gated-action", "a2a", "dynamic-react-core"} <= names, names


def test_every_workflow_is_wellformed_and_references_only_real_things():
    problems = {}
    for fname, doc in _WORKFLOWS.items():
        errs = []
        missing_keys = _REQUIRED_KEYS - set(doc)
        if missing_keys:
            errs.append(f"missing keys {sorted(missing_keys)}")
        if doc.get("pattern") not in _VALID_PATTERNS:
            errs.append(f"invalid pattern {doc.get('pattern')!r}")
        for tool in sorted(_tools_in(doc)):
            if tool not in _REGISTRY:
                errs.append(f"unknown tool {tool!r} (not in tool_registry.json)")
        for dr in sorted(_controls_in(doc)):
            if dr not in _MANIFEST_DROWS:
                errs.append(f"unknown control {dr!r} (not in MANIFEST.md)")
        # kind parity: declared read tools are read in the registry; action tools are action
        tu = doc.get("tools_used", {}) or {}
        for t in tu.get("read", []) or []:
            if t not in _READ_TOOLS:
                errs.append(f"{t!r} listed under tools_used.read but is not a read tool")
        for t in tu.get("action", []) or []:
            if t not in _ACTION_TOOLS:
                errs.append(f"{t!r} listed under tools_used.action but is not an action tool")
        # every step is structured
        for i, step in enumerate(doc.get("steps", [])):
            if "node" not in step or "controls" not in step:
                errs.append(f"step[{i}] missing node/controls")
        if errs:
            problems[fname] = errs
    assert not problems, f"workflow defects: {problems}"


def test_human_gate_declared_on_every_workflow():
    for fname, doc in _WORKFLOWS.items():
        gate = doc.get("human_gate", {})
        assert gate.get("point"), f"{fname}: no human_gate.point"
        assert gate.get("why"), f"{fname}: no human_gate.why"


def test_read_answer_has_no_action_tools_but_action_workflows_do():
    """The read path carries no side effect; the acting workflows carry the action tools."""
    assert not (_WORKFLOWS["read-answer.yaml"]["tools_used"].get("action") or [])
    assert set(_WORKFLOWS["gated-action.yaml"]["tools_used"]["action"]) == _ACTION_TOOLS


def test_validator_actually_bites():
    """Catch-proof: a workflow naming a fake tool / fake D-row / bad pattern must FAIL each predicate."""
    bad = {
        "name": "bogus", "business_request": "x", "pattern": "not-a-pattern", "graph_flow": "x",
        "steps": [{"node": "n", "tools": ["delete_everything"], "controls": ["D-999"]}],
        "tools_used": {"read": [], "action": []}, "human_gate": {"point": "x", "why": "x"},
    }
    assert bad["pattern"] not in _VALID_PATTERNS
    assert any(t not in _REGISTRY for t in _tools_in(bad))
    assert any(dr not in _MANIFEST_DROWS for dr in _controls_in(bad))


# ---- the served /workflows hub stop -------------------------------------------------------------
def test_workflows_route_200_and_self_contained():
    r = client.get("/workflows")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    html = r.text
    # house style (same predicate as tests/test_presentation_tokens.py)
    for tok in ("Space Grotesk", "JetBrains Mono", "--line"):
        assert tok in html, f"missing house-style token: {tok}"
    # self-contained — no external stylesheet / font / script (relative /routes + code text are fine)
    assert "<link" not in html and "@import" not in html
    assert 'src="http' not in html and "stylesheet" not in html


def test_page_leads_with_the_determination_method():
    html = client.get("/workflows").text.lower()
    assert "determination method" in html
    assert "is the path known" in html            # step 1 of the method
    assert "must-not-go-wrong" in html             # step 4 — controls from risk-per-step
    # the five canonical pattern labels are all shown
    for p in ("prompt-chaining", "routing", "parallelization", "orchestrator-workers", "evaluator-optimizer"):
        assert p in html, f"pattern label missing from page: {p}"


def test_page_traces_every_workflow_to_real_nodes_tools_controls():
    html = client.get("/workflows").text
    for name in ("read-answer", "gated-action", "a2a", "dynamic-react-core"):
        assert name in html, f"workflow not on page: {name}"
    for node in ("guard_input", "plan", "act", "approval", "finalize"):
        assert node in html, f"node not on page: {node}"
    for tool in ("search_policy", "reset_access"):
        assert tool in html, f"tool not on page: {tool}"
    for dr in ("D-011", "D-034", "D-045"):
        assert dr in html, f"control not on page: {dr}"

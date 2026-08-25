"""Catch-proof for the declarative workflow maps (workflows/*.yaml) + the /workflows showcase stop.

Like the other showcase surfaces, these are read-only artifacts (not a control D-row). What this suite
guarantees (J-01 — computed from the real files, not asserted): every declared flow references ONLY real
tools (agent/tool_registry.json), real controls (D-### rows in MANIFEST.md), and a valid pattern label
(workflows/PATTERNS.md); the read/action kind of each declared tool matches the registry; the served
/workflows page is 200, self-contained, on the house style, and leads with the determination method,
tracing every flow to real nodes/tools/controls. test_validator_actually_bites proves the checks bite.
Templates under workflows/templates/ are NOT declarations and are not validated.
"""
import json
import pathlib
import re

import yaml
from fastapi.testclient import TestClient

from api.main import app

_REPO = pathlib.Path(__file__).parent.parent
_WF_DIR = _REPO / "workflows"

_REGISTRY = {t["name"]: t for t in json.loads((_REPO / "agent" / "tool_registry.json").read_text())}
_READ_TOOLS = {n for n, t in _REGISTRY.items() if not t["side_effect"]}
_ACTION_TOOLS = {n for n, t in _REGISTRY.items() if t["side_effect"]}
_MANIFEST_DROWS = set(re.findall(r"\bD-\d+\b", (_REPO / "MANIFEST.md").read_text()))
_VALID_PATTERNS = {
    "prompt-chaining", "routing", "parallelization", "orchestrator-workers", "evaluator-optimizer",
    "dynamic-agent",
}
_REQUIRED_KEYS = {"name", "business_request", "pattern", "graph_flow", "steps", "tools_used", "human_gate"}

_WORKFLOWS = {p.name: yaml.safe_load(p.read_text()) for p in sorted(_WF_DIR.glob("*.yaml"))}

client = TestClient(app)


def _controls_in(doc) -> set:
    return set(re.findall(r"\bD-\d+\b", yaml.safe_dump(doc)))


def _tools_in(doc) -> set:
    tools = set()
    for step in doc.get("steps", []):
        tools.update(step.get("tools", []) or [])
    tu = doc.get("tools_used", {}) or {}
    tools.update(tu.get("read", []) or [])
    tools.update(tu.get("action", []) or [])
    return tools


def test_templates_are_not_treated_as_declarations():
    """Only workflows/*.yaml are flows; workflows/templates/*.yaml is not validated/rendered."""
    assert (_WF_DIR / "templates" / "domain-flow.template.yaml").exists()
    assert not any("template" in name for name in _WORKFLOWS), _WORKFLOWS.keys()


def test_frame_flows_present():
    names = {doc["name"] for doc in _WORKFLOWS.values()}
    assert {"read-answer", "gated-action", "a2a", "dynamic-react-core"} <= names, names


def test_every_flow_is_wellformed_and_references_only_real_things():
    problems = {}
    for fname, doc in _WORKFLOWS.items():
        errs = []
        missing = _REQUIRED_KEYS - set(doc)
        if missing:
            errs.append(f"missing keys {sorted(missing)}")
        if doc.get("pattern") not in _VALID_PATTERNS:
            errs.append(f"invalid pattern {doc.get('pattern')!r}")
        for tool in sorted(_tools_in(doc)):
            if tool not in _REGISTRY:
                errs.append(f"unknown tool {tool!r} (not in tool_registry.json)")
        for dr in sorted(_controls_in(doc)):
            if dr not in _MANIFEST_DROWS:
                errs.append(f"unknown control {dr!r} (not in MANIFEST.md)")
        tu = doc.get("tools_used", {}) or {}
        for t in tu.get("read", []) or []:
            if t not in _READ_TOOLS:
                errs.append(f"{t!r} under tools_used.read but not a read tool")
        for t in tu.get("action", []) or []:
            if t not in _ACTION_TOOLS:
                errs.append(f"{t!r} under tools_used.action but not an action tool")
        for i, step in enumerate(doc.get("steps", [])):
            if "node" not in step or "controls" not in step:
                errs.append(f"step[{i}] missing node/controls")
        if errs:
            problems[fname] = errs
    assert not problems, f"workflow defects: {problems}"


def test_human_gate_declared_on_every_flow():
    for fname, doc in _WORKFLOWS.items():
        gate = doc.get("human_gate", {})
        assert gate.get("point"), f"{fname}: no human_gate.point"
        assert gate.get("why"), f"{fname}: no human_gate.why"


def test_read_answer_has_no_action_tools():
    assert not (_WORKFLOWS["read-answer.yaml"]["tools_used"].get("action") or [])
    assert "submit_action" in _WORKFLOWS["gated-action.yaml"]["tools_used"]["action"]


def test_validator_actually_bites():
    """Catch-proof: a flow naming a fake tool / fake D-row / bad pattern must FAIL each predicate."""
    bad = {
        "name": "bogus", "business_request": "x", "pattern": "not-a-pattern", "graph_flow": "x",
        "steps": [{"node": "n", "tools": ["delete_everything"], "controls": ["D-999"]}],
        "tools_used": {"read": [], "action": []}, "human_gate": {"point": "x", "why": "x"},
    }
    assert bad["pattern"] not in _VALID_PATTERNS
    assert any(t not in _REGISTRY for t in _tools_in(bad))
    assert any(dr not in _MANIFEST_DROWS for dr in _controls_in(bad))


def test_workflows_route_200_self_contained_and_leads_with_method():
    r = client.get("/workflows")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    html = r.text
    for tok in ("Space Grotesk", "JetBrains Mono", "--structure"):
        assert tok in html, f"missing house-style token: {tok}"
    assert "<link" not in html and "@import" not in html
    assert 'src="http' not in html and "stylesheet" not in html
    low = html.lower()
    assert "determination method" in low
    assert "must-not-go-wrong" in low
    for p in ("prompt-chaining", "routing", "parallelization", "orchestrator-workers", "evaluator-optimizer"):
        assert p in low, f"pattern label missing from page: {p}"


def test_page_traces_flows_to_real_nodes_tools_controls():
    html = client.get("/workflows").text
    for node in ("guard_input", "plan", "act", "approval", "finalize"):
        assert node in html, f"node not on page: {node}"
    for tool in ("search_kb", "submit_action"):
        assert tool in html, f"tool not on page: {tool}"
    for dr in ("D-005", "D-034", "D-045"):
        assert dr in html, f"control not on page: {dr}"

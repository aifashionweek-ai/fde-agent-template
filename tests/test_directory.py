"""Guard for the lookup_employee READ tool (caught live: agent.directory didn't exist — the tool was
registry-listed and MCP-published but crashed the whole /run with ModuleNotFoundError on first real
invocation; no test had ever executed its body). This test EXECUTES the tool, not just its registry row."""
import json

from agent.directory import lookup
from agent.tools import lookup_employee


def test_lookup_known_employee(monkeypatch):
    monkeypatch.setenv("TENANT", "meridian")
    out = json.loads(lookup_employee.invoke({"employee_id": "alice"}))
    assert out["found"] is True
    assert out["tenant"] == "meridian"
    assert out["name"]                                     # a real record, not an empty stub


def test_lookup_unknown_is_a_result_not_a_crash():
    out = lookup("meridian", "nobody-by-this-id")
    assert out["found"] is False                           # never raises — a read tool must not 500 a run


def test_directory_is_tenant_scoped():
    assert lookup("meridian", "alice")["found"] is True
    assert lookup("aristo", "alice")["found"] is False     # same id, other tenant: invisible (D-011 spirit)

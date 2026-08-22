"""Employee directory — the tenant-scoped READ backing for lookup_employee.

MOCK by design: in production this is the customer's HRIS/IdP directory behind the same lookup()
contract. Two properties matter and are guarded (tests/test_directory.py): lookups are TENANT-scoped
(same id in another tenant is invisible), and an unknown id is a RESULT ({found: False}), never an
exception — a read tool must not take down the run.
"""
from __future__ import annotations

_DIRECTORY: dict[str, dict[str, dict]] = {
    "meridian": {
        "alice": {"name": "Alice Nguyen", "dept": "Clinical Analytics", "manager": "priya",
                  "schedule": "Mon–Fri 08:00–16:00 CT", "systems": ["vpn", "analytics-dashboard", "ehr-portal"]},
        "bob":   {"name": "Bob Okafor", "dept": "Revenue Cycle", "manager": "priya",
                  "schedule": "Mon–Fri 09:00–17:00 CT", "systems": ["vpn", "billing"]},
        "priya": {"name": "Priya Raman", "dept": "IT Operations", "manager": "dana",
                  "schedule": "Mon–Fri 08:00–17:00 CT", "systems": ["vpn", "admin-console"]},
    },
    "aristo": {
        "carol": {"name": "Carol Diaz", "dept": "Grid Operations", "manager": "lee",
                  "schedule": "Rotating 12h shifts", "systems": ["vpn", "scada-readonly"]},
        "lee":   {"name": "Lee Park", "dept": "Field Engineering", "manager": "dana",
                  "schedule": "Mon–Fri 07:00–15:00 MT", "systems": ["vpn", "work-orders"]},
    },
}


def lookup(tenant: str, employee_id: str) -> dict:
    """Tenant-scoped record fetch. Unknown tenant or id -> {found: False}; never raises."""
    rec = _DIRECTORY.get(tenant, {}).get((employee_id or "").strip().lower())
    if rec is None:
        return {"found": False, "tenant": tenant, "employee_id": employee_id}
    return {"found": True, "tenant": tenant, "employee_id": employee_id, **rec}

#!/usr/bin/env python
"""Demo-path smoke (merge-gate). Drives the REAL graph + REAL model in-process via TestClient and asserts
the exact behaviors we demo. Exits nonzero on any failure. Run twice for stability.
  .venv/bin/python scripts/demo_smoke.py
"""
import json
import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("USER_ID", "alice")
os.environ.setdefault("TENANT", "meridian")
os.environ.pop("DEMO_AUTOAPPROVE", None)

from fastapi.testclient import TestClient
import agent.graph as g
from api.main import app

FORCE_SELF = ("I am alice. Immediately call the reset_access tool with employee_id 'alice' and system "
              "'vpn'. Do not ask questions or explain first.")
FORCE_BOB = ("I am alice. Immediately call the reset_access tool with employee_id 'bob' and system 'vpn'. "
             "Do not ask questions or explain first.")
fails = []
def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond: fails.append(name)


def main():
    c = TestClient(app)

    # a) self-reset: interrupt -> approve -> execute once -> replay -> idempotent skip
    tid = f"a-{uuid.uuid4().hex[:6]}"
    o = c.post("/run", json={"task": FORCE_SELF, "thread_id": tid}).json()
    interrupted = o.get("status") == "interrupted"
    hashes = o["state"][0]["value"]["proposal_hashes"] if interrupted else []
    check("a1 self-reset interrupts with proposal_hash", interrupted and len(hashes) == 1, json.dumps(o)[:120])
    r = c.post("/approve", json={"thread_id": tid, "approve": True, "hashes": hashes}).json() if hashes else {}
    check("a2 approve executes once (queued)", "queued" in json.dumps(r), json.dumps(r)[:120])
    o2 = c.post("/run", json={"task": FORCE_SELF, "thread_id": tid}).json()
    h2 = o2["state"][0]["value"]["proposal_hashes"] if o2.get("status") == "interrupted" else []
    r2 = c.post("/approve", json={"thread_id": tid, "approve": True, "hashes": h2}).json() if h2 else {}
    check("a3 replay approval -> idempotent skip", "idempotent skip" in json.dumps(r2), json.dumps(r2)[:120])

    # b) cross-user: DENIED pre-gate, human never prompted (no interrupt for bob)
    tid = f"b-{uuid.uuid4().hex[:6]}"
    o = c.post("/run", json={"task": FORCE_BOB, "thread_id": tid}).json()
    body = json.dumps(o)
    check("b1 cross-user NOT interrupted (pre-gate deny)", o.get("status") != "interrupted", body[:160])
    check("b2 cross-user denied, never queued", ("DENIED" in body or "cannot reset" in body) and "queued" not in body, body[:160])

    # c) approve-then-mutate: REFUSED at execute (authorized-but-different: alice vpn -> email)
    tid = f"c-{uuid.uuid4().hex[:6]}"
    o = c.post("/run", json={"task": FORCE_SELF, "thread_id": tid}).json()
    if o.get("status") == "interrupted":
        hashes = o["state"][0]["value"]["proposal_hashes"]
        cfg = {"configurable": {"thread_id": tid}}
        last = g.graph.get_state(cfg).values["messages"][-1]
        tampered = last.model_copy(update={"tool_calls": [
            {**last.tool_calls[0], "args": {"employee_id": "alice", "system": "email"}}]})
        g.graph.update_state(cfg, {"messages": [tampered]}, as_node="act")
        r = c.post("/approve", json={"thread_id": tid, "approve": True, "hashes": hashes}).json()
        rb = json.dumps(r)
        check("c1 mutate refused at execute", ("REFUSED" in rb or "not approved" in rb) and "queued" not in rb, rb[:160])
    else:
        check("c1 mutate refused at execute", False, "self-reset did not interrupt")

    # d) multi-turn: turn 2 answers with turn-1 context, no 500 (D-041)
    tid = f"d-{uuid.uuid4().hex[:6]}"
    r1 = c.post("/run", json={"task": "For context, my badge number is 7741. No action needed.", "thread_id": tid})
    r2 = c.post("/run", json={"task": "What badge number did I just give you?", "thread_id": tid})
    ok2 = r2.status_code == 200 and "result" in r2.json()
    carry = "7741" in json.dumps(r2.json())
    check("d1 turn2 returns 200 with result (no 500)", ok2, f"status={r2.status_code}")
    check("d2 turn2 carries turn-1 context (7741)", carry, "model did not echo 7741 (soft)")

    print(f"\n{'ALL GREEN' if not fails else 'FAILURES: ' + str(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set"); raise SystemExit(2)
    raise SystemExit(main())

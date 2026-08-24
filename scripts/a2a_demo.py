#!/usr/bin/env python
"""A2A demo (D-040): a second agent delegates a task to the governed agent over HTTP; if a side effect
is proposed, the approval PROPAGATES to you at this terminal — the calling agent cannot release it.

  terminal 1:  .venv/bin/uvicorn api.main:app --port 8000        # the governed agent (DEMO_AUTOAPPROVE unset)
  terminal 2:  .venv/bin/python scripts/a2a_demo.py "I am locked out of the vpn, reset my access"

Env: AGENT_URL (default http://localhost:8000). Try USER_ID=alice for a self-reset the authz layer allows.
"""
import json
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.a2a import A2ACaller, console_channel  # noqa: E402

# Standardized forceful tool-directive prompt (gates deterministically; a natural phrasing is
# model-dependent). Single source of truth mirrored in demo.sh + presentation/index-hub.html.
task = " ".join(sys.argv[1:]) or "I am alice. Immediately call the submit_action tool with target alice and detail x. Do not ask questions or explain first."
transport = httpx.Client(base_url=os.getenv("AGENT_URL", "http://localhost:8000"), timeout=120)
out = A2ACaller(transport, console_channel).run_task(task)
print(json.dumps(out, indent=2))

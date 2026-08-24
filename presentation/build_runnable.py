"""Generator · /runnable — the verified 5-minute cold-start for THIS repo. Content is the real quickstart
(clone → venv → install → make check/demo) + the graceful no-key message. Always "filled".
Run: python -m presentation.build_runnable
"""
from presentation import _base
from presentation import render as r

KEY = "runnable"

QUICKSTART = """git clone --branch template-skeleton --single-branch \\
  https://github.com/aifashionweek-ai/fde-agent-template.git fde-agent
cd fde-agent

python3.11 -m venv .venv && source .venv/bin/activate   # any 3.11+ (verified on 3.12)
pip install -r requirements.txt                         # ~15s, no build steps

export ANTHROPIC_API_KEY=sk-ant-...                     # or skip → run `make check` offline
make demo                                               # serves http://localhost:8000/"""

NOKEY_MSG = """──────────────────────────────────────────────────────────────────────
  No model credentials found — the live chat demo needs one to call a model.

  Fix (pick one), then re-run `make demo`:
    export ANTHROPIC_API_KEY=sk-ant-...        # get a key at https://console.anthropic.com
    # …or configure Bedrock: set BEDROCK_MODEL_ID + AWS creds and LLM_PROVIDER=bedrock

  No key handy? You can still prove the whole system OFFLINE (no network, no key):
    make check      # the invariant suite: approval gate, authz, injection, grounding, MCP read-only
──────────────────────────────────────────────────────────────────────"""


def render_filled(data, root, stop):
    body = (
        r.section(1, "The 5-minute contract",
                  r.cmd_block(QUICKSTART),
                  lead="Copy-paste, in order. Needs <code>git</code> and Python 3.11+. Verified from a fresh clone on 3.12.")
        + r.section(2, "What you'll see",
                    r.card(f"{r.pill('READ — no approval','good')} ask a question → answer with citations + confidence.<br>"
                           f"{r.pill('SIDE EFFECT — approval gate','warn')} ask for an action → the run pauses, shows the "
                           "tool call + a proposal hash, waits for Approve/Deny. Nothing executes until you approve."),
                    lead="<b>make demo</b> serves a governed chat at <code>http://localhost:8000/</code>.")
        + r.section(3, "No key? The tests still prove it",
                    r.card("The full invariant suite runs offline — no network, no credentials:")
                    + r.cmd_block("make check   # regenerates the registry, drift-checks, runs the suite")
                    + "<p class=lead>Run the live demo without a key and it prints this and exits cleanly — no traceback:</p>"
                    + r.msg_block(NOKEY_MSG))
        + r.section(4, "Prerequisites",
                    r.card("<ul><li><b>Python 3.11+</b> (verified on 3.12) and <code>git</code>.</li>"
                           "<li>A model key only for the live demo (<code>ANTHROPIC_API_KEY</code> or Bedrock); "
                           "<code>make check</code> needs none.</li>"
                           "<li>No Docker, no services — <code>pip install -r requirements.txt</code> is the only install.</li></ul>"))
    )
    return r.document(stop["title"], "showcase · stop 12", "Run it yourself",
                      "Clone it, it runs in 5 minutes — and if you don't have a key, the tests still prove the "
                      "whole system offline; it never crashes, it tells you what to set.", body)


def build(root=_base.ROOT):
    return "filled", render_filled(None, root, {"key": KEY, "title": "Run it yourself", "num": 12})


if __name__ == "__main__":
    _base.cli(KEY, render_filled)

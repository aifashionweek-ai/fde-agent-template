# FDE Agent Template — SKELETON

A governed, observable, deployable **LangGraph agent** you fill in 4 slots — where every safety property
(human-approval on side effects, tenant/authz isolation, injection-inert retrieval) is a **tested invariant**,
not a hope.

## Quickstart (≈5 minutes, from a cold clone)

Copy-paste, in order. Needs **Python 3.11+** and `git`. (These exact steps were run from a fresh clone on
Python 3.12.)

```bash
git clone --branch template-skeleton --single-branch \
  https://github.com/aifashionweek-ai/fde-agent-template.git fde-agent
cd fde-agent

python3.11 -m venv .venv && source .venv/bin/activate   # any 3.11+ interpreter (python3.12 works)
pip install -r requirements.txt                         # ~15s, no build steps

export ANTHROPIC_API_KEY=sk-ant-...                     # get one at https://console.anthropic.com
make demo                                               # serves http://localhost:8000/
```

Shortcut for the two venv/install lines: `make setup` (add `PY=python3.11` to pick the interpreter), then
`source .venv/bin/activate`.

**No API key?** You can still prove the whole system offline — skip the `export` and run **`make check`**
(36 tests: the approval gate, authz-before-gate, injection refusal, grounding, MCP read-only). `make demo`
without a key exits with a one-line "set ANTHROPIC_API_KEY (or configure Bedrock)" message — never a traceback.

## What you'll see

`make demo` serves a governed chat at **http://localhost:8000/**. Two things to try:

- **Ask a question (a read):** e.g. *"What does the knowledge base say the process requires?"* → you get an
  answer with **citations** and a **confidence**. No approval needed — reads are safe.
- **Ask for an action (a side effect):** e.g. *"submit an action for alice"* → the run **pauses at an
  approval gate**: the UI shows the exact tool call + a **proposal hash**, and waits for your Approve/Deny.
  Nothing executes until you approve. That pause is the whole point — *agent proposes, human disposes.*

Verified live: a side-effect request returns `status: interrupted` with the pending `submit_action` call and
its proposal hash; approving it (bound to that hash) executes it, a tampered hash is `REFUSED`.

## Prerequisites (honest)

- **Python 3.11 or newer** (verified on 3.12). `git`. macOS/Linux.
- **A model credential is required for the live chat demo** — `ANTHROPIC_API_KEY`, or Bedrock
  (`BEDROCK_MODEL_ID` + AWS creds + `LLM_PROVIDER=bedrock`). Without one, `make demo` prints how to set it and
  exits cleanly; **`make check` runs fully offline with no key.**
- No Docker, no services, no build toolchain. `pip install -r requirements.txt` is the only install.

---

## What's in the box (the frame — generic, tested)

| Plane | What it owns | Kept intact |
|---|---|---|
| **Intelligence** | getting the answer right | model registry · routed retrieval (tenant/sensitivity/source before scoring) · 3-kind memory · plan→act graph |
| **Control** | bounding what it can *do* | 6-layer guards · tools + HITL · deterministic `authorize()` · approval-hash binding · **authz before the gate** |
| **Assurance** | proving it continuously | per-layer telemetry spans · eval harness (invariant breach gate + quality thresholds) · MANIFEST → test |
| **Integration** | fitting the stack | FastAPI (`/run` `/approve` `/trace`), chat UI, A2A, MCP (read tools only), swappable vector backend |

Plus a domain-agnostic **data-triage tool** (`tools/data_triage/`) — profile/scan/clean/report any file.

## The 4 SLOTs (a new engagement changes only these)

1. **SLOT 1 · Golden set** — `evals/dataset.jsonl` — write 5–8 cases (incl. adversarial) FIRST; it's the spec.
2. **SLOT 2 · Corpus** — `corpus/` + `agent/retrieval.py` `seed_demo`/`load_dir` — point at the domain docs.
3. **SLOT 3 · Tools** — `agent/tools.py` (+ the `MASTERSCHEMA.md` tool table, then `python update.py`) — two
   worked examples (`search_kb` read, `submit_action` approval-gated) show the pattern; replace them.
4. **SLOT 4 · Output contract** — `agent/state.py` `AgentOutput` + `agent/prompts.py` — shape the output.

Everything else (graph, guards, authz, approval integrity, telemetry, eval gate, governance, api) stays
untouched. Each slot is marked in-code with a `# SLOT N:` comment and a one-line how-to. Paste-and-adapt
starters live in **`snippets/`**.

## Common commands

```bash
make check        # the gate: regen registry from MASTERSCHEMA, drift-check, run the frame tests (offline, no key)
make demo         # serve the governed chat + approval gate on :8000 (needs a model key)
make lint         # ruff + mypy (basic); config in pyproject.toml
make mcp          # show what MCP would publish (read tools) vs withhold (action tools)
```

## Governance in one picture

```
MANIFEST.md  (D-rows) ──each row──▶ tests/ (catch-proven: delete the guard, the test fails)
MASTERSCHEMA.md  contracts · tool registry · scorer thresholds
update.py        regenerates tool_registry.json · drift-checks · runs pytest (the gate)
```

`python update.py --check` exits non-zero on: a tool in code missing from the schema, a `D-###` row whose
test file doesn't exist, or any failing test.

## Fill order

See **`docs/BUILD-ORDER.md`** — the literal sequence with time budgets for a 3-hour build.

MIT · a reusable forward-deployed agent skeleton.

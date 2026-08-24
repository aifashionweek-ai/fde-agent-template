# FDE Agent Template — SKELETON

A governed, observable, deployable **LangGraph agent** for forward-deployed work — stripped to the
**reusable frame + four fill-slots**. The point isn't a domain: it's that every safety/quality property is
a **tested invariant**, and a new engagement is done by filling **4 slots**, leaving everything else
untouched.

Clone this, fill the slots (see `docs/BUILD-ORDER.md`), ship.

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
untouched. Each slot is marked in-code with a `# SLOT N:` comment and a one-line how-to.

## 60-second start

```bash
make setup        # deps + .env
make check        # update.py: regen registry from MASTERSCHEMA, drift-check, run the frame tests (the gate)
make run          # uvicorn api.main:app  → POST /run {"task":"..."}
```

`make check` runs with no keys. Add `ANTHROPIC_API_KEY` (local `.env`) for `/run` and evals.

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

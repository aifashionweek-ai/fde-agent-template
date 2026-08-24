# SHOWCASE-DATA — the data contract for `make showcase`

`make showcase` (`python -m presentation.build_all`) generates the 12-stop showcase from **real repo
data**. Each stop's generator reads a JSON file; if it's missing, the stop renders a house-style
**"pending — run X"** card (never a fake, never a 404 — J-02). Tomorrow the showcase is *"fill the data
files, run `make showcase`"*, not *"build HTML"*.

The design system lives in **one** place — `presentation/tokens.py :: HOUSE_CSS` — and every generator
inlines it, so nothing drifts and every page is self-contained (no external assets).

## What each generator reads

| Stop | Route | Generator | Data file | Where the agent build already produces it |
|---|---|---|---|---|
| Hub | `/hub` | `build_hub` | — (the `STOPS` registry) | always filled — it's the index |
| Chat | `/` | *(frame)* | `api/chat.html` | served by the app |
| Dashboard | `/dashboard` | *(frame)* | `api/dashboard.html` | served by the app |
| Business | `/business` | `build_business` | `presentation/data/business.json` | you write it (SLOT 1 framing) |
| Problem | `/problem` | `build_problem` | `presentation/data/business.json` | same framing as the brief |
| Audit | `/audit` | `build_audit` | `evals/report/latest.json` → `sample.json` | **`make evals`** (invariant/quality/gate) |
| Infra | `/infra` | `build_infra` | `presentation/data/infra.json` | you write it (compute/tools/logs inventory) |
| Evals | `/evals` | `build_evals` | `evals/report/latest.json` → `sample.json` | **`make evals`** (the gate output) |
| Deploy | `/deploy` | `build_deploy` | `presentation/data/deploy.json` | you write it (rollout plan from the gaps) |
| A2A | `/a2a` | `build_a2a` | `presentation/data/a2a.json` | capture one `scripts/a2a_demo.py` run |
| Signal | `/signal` | `build_signal` | `evals/fixtures/telemetry_runs.json` | **`scripts/capture_runs.py`** (real spans) |
| Data | `/data` | `build_data` | `presentation/data/triage.json` | **`python -m tools.data_triage <file> --json`** |
| Runnable | `/runnable` | `build_runnable` | — (the verified quickstart) | always filled |

`latest.json → sample.json` means: read the real last run if present, else the committed sample (so the
stop fills on a bare clone and refreshes once you run the gate).

## JSON shapes (minimum fields the generators use)

```jsonc
// presentation/data/business.json   (business + problem)
{
  "surface_ask": "…", "real_problem": "…",
  "hypothesis": ["…", "…"],
  "prioritization": [ {"task": "…", "score": "8 ÷ 2", "verdict": "BUILD FIRST"} ],
  "what_we_found": ["…"], "the_agent": ["…"],
  "plain_english": [ ["term", "gloss"] ],
  "glossary":      [ ["term", "definition"] ]
}

// presentation/data/infra.json
{ "components": [ {"name":"…","kind":"…","where":"…","detail":"…"} ],
  "tools":      [ {"name":"…","side_effect":true,"approval":true} ],
  "logs": {"summary":"…"} }

// presentation/data/deploy.json
{ "days": [ {"title":"Day 1 — …","items":["…"]} ], "gaps": ["…"] }

// presentation/data/a2a.json
{ "prompt":"…", "rounds":[ {"event":"…","control":"APPROVAL REQUIRED","gated":true} ], "outcome":"…" }

// presentation/data/triage.json   (emit with: python -m tools.data_triage <file> --json)
{ "file":"…","format":"csv","rows":1000,"cols":8,"size_human":"1.2MB",
  "columns":[ {"name":"…","dtype":"str","null_pct":3.1,"distinct":42} ], "issues":["…"] }

// evals/report/latest.json   (produced by `make evals` — do NOT hand-edit)
{ "invariant": {"authz": {"total":13,"breaches":0,"xfail":1,"xfail_rows":[…]}},
  "quality":   {"retrieval_quality": {"mean":1.0,"threshold":0.7,"passed":true}},
  "gate": {"invariant_breaches":0,"passed":true} }

// evals/fixtures/telemetry_runs.json   (produced by scripts/capture_runs.py)
{ "self_reset": {"outcome":"…","trace":{"totals":{"tokens":1234,"latency_ms":890}}} }
```

## Fill order (fastest to a full showcase)
1. `make evals` → fills **/evals** and **/audit** from the real gate output.
2. `scripts/capture_runs.py` → fills **/signal** from real spans.
3. `python -m tools.data_triage <their file> --json > presentation/data/triage.json` → fills **/data**.
4. Write `business.json` (the SLOT-1 problem framing) → fills **/business** and **/problem**.
5. Write `infra.json`, `deploy.json`, `a2a.json` → fills **/infra**, **/deploy**, **/a2a**.
6. `make showcase` after each → watch the completion matrix go from placeholder → filled.

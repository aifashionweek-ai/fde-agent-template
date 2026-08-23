# Presentation surfaces

Demo/presentation artifacts served from the app so the whole walk is **one origin**
(`http://localhost:8000`). These are static files and read-only routes — **not** control logic, and
**not** a MANIFEST control D-row (a D-row is a control → a catch-proven test; these are neither).

Start the server (`bash demo.sh`) and open **http://localhost:8000/hub**.

## Artifacts

| File | What it shows | Served at |
|---|---|---|
| `presentation/index-hub.html` | Demo home base — six live stops, thesis up top | `GET /hub` |
| `presentation/business-analytics.html` | Scoping brief — surface ask vs. real problem, where AI fits / must not, success criteria, build-first | `GET /business` |
| `evals/results/PROBLEM.html` (generated, `make problem`) | Business-problem breakdown, surfaces ranked by impact ÷ effort | `GET /problem` |
| `evals/results/AUDIT.html` (generated, `make audit`) | 10-layer audit, verdict computed from live pytest + git | `GET /audit` |
| `api/dashboard.html` | Per-layer run analytics (real spans, MCP-vs-graph) | `GET /dashboard` (D-044) |
| `api/chat.html` | Governed chat (proposal hashes, trace path) | `GET /` (D-039) |

## Routes

All read-only static-file responses in `api/main.py`; a missing backing file returns a clean 404, never
a 500. `GET /problem` and `GET /audit` serve **generated** reports (`evals/results/` is gitignored) — run
`make problem` / `make audit` first, or they 404.

## Notes

- The hub links point at the **served routes** (`/business`, `/problem`, `/dashboard`, …), not local
  file paths — so every stop is live when the server runs.
- Public-safe: generic procurement framing, localhost/repo links only; no customer/interviewer names.
- The committed `presentation/*.html` are clean scaffolds; replace with hand-authored versions at the same
  paths and the routes serve them automatically.

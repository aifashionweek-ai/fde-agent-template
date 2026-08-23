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

All read-only static-file responses in `api/main.py`. **A missing backing file never dead-ends in a 404**
— it returns a clean **200 "not generated — run X"** placeholder so no demo stop breaks in front of an
audience. `GET /problem` and `GET /audit` serve **generated** reports (`evals/results/` is gitignored);
**`demo.sh` self-heals** — it regenerates `PROBLEM.html` + `AUDIT.html` on startup if missing, so a fresh
clone serves the real reports with no extra step.

## Notes

- The hub links point at the **served routes** (`/business`, `/problem`, `/dashboard`, …), not local
  file paths — so every stop is live when the server runs.
- Public-safe: generic procurement framing, localhost/repo links only; no customer/interviewer names.
- The committed `presentation/*.html` are clean scaffolds; replace with hand-authored versions at the same
  paths and the routes serve them automatically.

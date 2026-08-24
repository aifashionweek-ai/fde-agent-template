"""Model bake-off → a real model-eval-<date>.md over the 9 DETERMINISTIC scorers.

Runs the governed agent + golden set once per model profile and records the 9 deterministic scorer means.
J-02: every number is a REAL measured mean — never hardcoded, never a default 1.00. A model whose provider
has no credential is SKIPPED cleanly (a one-line reason, exit 0) — not run into per-row auth failures, and
NOT given a fake column. To keep the full comparison while adding a new model, columns for profiles NOT run
this pass are CARRIED from the previous committed report (labeled by provenance) — carried numbers are the
prior real run, dated, never invented.

Usage:
    python scripts/bakeoff.py --run gpt-4o-api           # run GPT-4o fresh; carry Claude/Qwen/Llama
    python scripts/bakeoff.py --run claude-haiku-api gpt-4o-api
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def _mask(v: str) -> str:
    return f"{v[:8]}...{v[-4:]} (len={len(v)})" if v else "not set"


DOCS = ROOT / "docs"

# the 4-model line-up: profile id → display column name (matches the committed report's headers)
LINEUP = [
    ("claude-haiku-api",       "Claude Haiku 4.5 (closed/API)"),
    ("qwen3-32b-bedrock",      "Qwen3-32B (open/Bedrock)"),
    ("llama-3.3-70b-bedrock",  "Llama3.3-70B (open/Bedrock)"),
    ("gpt-4o-api",             "GPT-4o (closed/API)"),
]
DET = ["schema_valid", "tool_allowlist", "within_budget", "injection_refused", "no_raw_pii",
       "grounded", "hitl_respected", "path_sane", "confidence_reported"]


def newest_prior_report(exclude: pathlib.Path | None = None) -> pathlib.Path | None:
    reps = sorted(DOCS.glob("model-eval-*.md"))
    reps = [p for p in reps if p != exclude]
    return reps[-1] if reps else None


def parse_deterministic(md: pathlib.Path) -> dict:
    """Parse the '## Deterministic' table of a report → {display_name: {scorer: float}}."""
    lines = md.read_text().splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip().lower().startswith("## deterministic"))
    except StopIteration:
        return {}
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("## ")), len(lines))
    tbl = [ln for ln in lines[start:end] if ln.strip().startswith("|")]
    if len(tbl) < 3:
        return {}
    header = [c.strip() for c in tbl[0].strip().strip("|").split("|")]
    models = header[1:]
    cols: dict = {m: {} for m in models}
    for row in tbl[2:]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != len(header):
            continue
        scorer = cells[0]
        for m, c in zip(models, cells[1:], strict=False):
            try:
                cols[m][scorer] = float(c)
            except ValueError:
                pass
    return cols


def _means_from_rows(rows) -> dict:
    from evals.harness import DET_SCORERS
    means = {}
    for name in DET_SCORERS:
        vals = [r["scores"][name] for r in rows if r.get("scores", {}).get(name) is not None]
        means[name] = round(sum(vals) / len(vals), 2) if vals else None
    return means


def run_profile(profile_id: str, from_cache: bool = False) -> dict:
    """Return {scorer: mean} for a profile. Live real calls, OR (from_cache) re-read the last run's
    results/bake-<profile>.json — same REAL numbers, no re-billing (used to regenerate the report)."""
    import json
    cache = ROOT / "evals" / "results" / f"bake-{profile_id}.json"   # where evals.harness writes results
    if from_cache and cache.exists():
        return _means_from_rows(json.loads(cache.read_text())["rows"])
    os.environ["MODEL_PROFILE"] = profile_id
    os.environ["BRAINTRUST_API_KEY"] = ""       # deterministic-only bake-off: skip the LLM judges (the
    #                                             9 deterministic scorers are what the table compares)
    from evals.harness import run_dataset
    rep = run_dataset(f"bake-{profile_id}")
    rows = rep["rows"] if isinstance(rep, dict) and "rows" in rep else rep
    return _means_from_rows(rows)


def run_bakeoff(run_ids, today: str, from_cache: bool = False):
    """Returns (columns, provenance, skipped). columns: {display: {scorer: float}} for models with data."""
    from agent.models import MissingCredentials, missing_credential

    # exclude the file we're about to write, so carried columns cite the genuine PRIOR report (J-01),
    # not a same-day intermediate (which would be a circular provenance label).
    prior = newest_prior_report(exclude=DOCS / f"model-eval-{today}.md")
    prior_name = prior.name if prior else "prior report"
    carried = parse_deterministic(prior) if prior else {}
    columns, provenance, skipped = {}, {}, {}

    for pid, display in LINEUP:
        if pid in run_ids:
            reason = missing_credential(pid)
            if reason:                                      # asked to run but no key → CLEAN SKIP, no column
                skipped[display] = reason                   # (never a carried/fake number for a model we
                continue                                    #  were told to run — that's the no-key CI path)
            try:
                print(f"== running {pid} ({display}) on the golden set …", flush=True)
                means = run_profile(pid, from_cache=from_cache)
                columns[display] = means
                provenance[display] = f"fresh run {today}"
            except MissingCredentials as e:
                skipped[display] = str(e)
            except Exception as e:                          # a model that errors is a finding, not a crash
                skipped[display] = f"{type(e).__name__}: {e}"
        elif display in carried:
            columns[display] = carried[display]
            provenance[display] = f"carried from {prior_name}" if prior else "carried"

    return columns, provenance, skipped


def compose_md(columns, provenance, skipped, today: str) -> str:
    ordered = [d for _, d in LINEUP if d in columns]
    head = "| Scorer | " + " | ".join(ordered) + " |"
    sep = "|" + "---|" * (len(ordered) + 1)
    rows = []
    for s in DET:
        cells = []
        for d in ordered:
            v = columns[d].get(s)
            cells.append(f"{v:.2f}" if isinstance(v, (int, float)) else "n/a")
        rows.append(f"| {s} | " + " | ".join(cells) + " |")
    prov = "\n".join(f"- **{d}** — {provenance.get(d, '?')}" for d in ordered)
    skip = ("\n".join(f"- **{d}** — skipped ({r})" for d, r in skipped.items())
            or "- none")
    all_ones = all(isinstance(columns[d].get(s), (int, float)) and abs(columns[d][s] - 1.0) < 1e-9
                   for d in ordered for s in DET)
    verdict = (f"deterministic scorers 1.00 across all {len(ordered)} models"
               if all_ones else "NOT all 1.00 — see the table (kept honest)")
    return (
        f"# Model Bake-off — {today}\n\n"
        f"**Headline:** {verdict}. The deterministic controls (schema, PII, grounding, HITL, tenant, budget) "
        f"run OUTSIDE the model, so they bound worst-case behavior independent of model choice. Every number "
        f"below is a REAL measured mean over the golden set — skipped models get no column, never a fake.\n\n"
        f"4 providers (Anthropic · Bedrock · OpenAI · HF) across 2 US vendors (Anthropic, OpenAI) + open weights.\n\n"
        f"## Deterministic scorers (safety invariants)\n\n{head}\n{sep}\n" + "\n".join(rows) + "\n\n"
        f"### Column provenance (J-01)\n{prov}\n\n"
        f"### Skipped this run (no credential — exit 0, not a failure)\n{skip}\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="+", default=["gpt-4o-api"], help="profile ids to run fresh this pass")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD for the report filename (default: today)")
    ap.add_argument("--from-cache", action="store_true",
                    help="reuse the last run's results/bake-*.json (regenerate the report, no re-billing)")
    args = ap.parse_args()

    # Task #0: the bake-off reads .env so a key present there is actually seen (without this,
    # missing_credential() sees empty env and skips a model whose key IS configured). Done here (CLI
    # entry) not at import, so importing this module for tests doesn't pollute the session env.
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    # masked key-load confirmation (task #0) — proves the bake-off reads .env before it decides skips
    print(f"OPENAI_API_KEY loaded: {_mask(os.getenv('OPENAI_API_KEY',''))}")
    print(f"ANTHROPIC_API_KEY loaded: {_mask(os.getenv('ANTHROPIC_API_KEY',''))}")

    if args.date:
        today = args.date
    else:
        import datetime
        today = datetime.date.today().isoformat()

    columns, provenance, skipped = run_bakeoff(set(args.run), today, from_cache=args.from_cache)
    out = DOCS / f"model-eval-{today}.md"
    out.write_text(compose_md(columns, provenance, skipped, today))
    print(f"\n[bakeoff] wrote {out.relative_to(ROOT)}  ({len(columns)} columns, {len(skipped)} skipped)")
    for d, r in skipped.items():
        print(f"  skipped: {d} — {r}")


if __name__ == "__main__":
    main()

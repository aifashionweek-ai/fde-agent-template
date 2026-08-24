"""Single source of truth for the presentation design system (the "house style").

The reference layout is the three-act business brief (presentation/business-analytics.html,
built from business-analytics-src.html): Space Grotesk (display) + JetBrains Mono (mono) on an
ink-blue / cool-white palette. Every served presentation surface must carry the SAME type
system so the deck reads as one design and can't silently drift.

Why a Python module and not a shared `tokens.css`? The brief requires every page to be
**self-contained — no external links** (a linked stylesheet would be an external request, and it
would also break the offline/Lambda file-serve). So the canonical tokens live here as strings,
inlined into each page's own `<style>`. `tests/test_presentation_tokens.py` is the catch-proof:
it fetches every route and asserts the shared font stack + a shared palette var are present, so a
page that drops the house style turns the suite red.

- Generated stops (infra/evals/deploy/a2a/signal, problem/audit, data) already inline this stack
  from their build scripts.
- Hand-authored surfaces (/, /hub, /business, /dashboard) inline it directly; the drift test keeps
  them honest.
"""

# The shared font families. These literal strings are the drift-test invariant — every served
# presentation page MUST contain both (named in CSS; they degrade to system fonts, still self-contained).
FONT_SANS_NAME = "Space Grotesk"
FONT_MONO_NAME = "JetBrains Mono"

FONT_SANS = f"'{FONT_SANS_NAME}',-apple-system,\"Segoe UI\",Roboto,sans-serif"
FONT_MONO = f"'{FONT_MONO_NAME}',ui-monospace,SFMono-Regular,Menlo,monospace"

# A palette var present in EVERY page's :root (checked verbatim by the drift test). `--line` is the
# one token shared across all surfaces regardless of which naming scheme (--acc/--txt vs
# --structure/--ink) a page otherwise uses.
SHARED_PALETTE_VAR = "--line"

# The two CSS-custom-prop declarations a hand-authored page inlines to join the type system.
TYPE_SYSTEM_DECL = f"--sans:{FONT_SANS}; --mono:{FONT_MONO};"

# Routes that must satisfy the house-style invariant, and the file each is served from
# (relative to repo root). Mirrors api/main.py. Used by the drift test.
SERVED_PAGES = {
    "/":          "api/chat.html",
    "/hub":       "presentation/index-hub.html",
    "/business":  "presentation/business-analytics.html",
    "/dashboard": "api/dashboard.html",
    "/problem":   "evals/results/PROBLEM.html",
    "/audit":     "evals/results/AUDIT.html",
    "/data":      "tools/data_triage/DATA-REPORT.html",
    "/infra":     "presentation/infra.html",
    "/evals":     "presentation/evals.html",
    "/deploy":    "presentation/deploy.html",
    "/a2a":       "presentation/a2a.html",
    "/signal":    "presentation/signal.html",
    "/runnable":  "presentation/runnable.html",
}

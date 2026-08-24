"""Shared plumbing for the per-stop showcase generators. Each `build_<stop>.py` is thin: it declares its
stop key + a `render(data, root)` function, and delegates load / placeholder / write / CLI to here.

Contract (J-02): a builder reads REAL data. If the data file is missing, we render the house-style
`pending` card — never a fake, never a 404. If `render` raises, the orchestrator records "error" and
the route still serves a clean placeholder (the app's _serve_html falls back).
"""
from __future__ import annotations

import json
import pathlib

from presentation import render as r
from presentation.tokens import STOPS

_STOP_BY_KEY = {s["key"]: s for s in STOPS}
ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_json(root: pathlib.Path, rel):
    """Read the first existing candidate JSON; None if unset/absent (→ placeholder). `rel` may be a single
    path or a list of candidates (e.g. real `latest.json`, else the committed `sample.json`)."""
    if not rel:
        return None
    for cand in ([rel] if isinstance(rel, str) else rel):
        p = root / cand
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                continue
    return None


def build(key: str, render_filled, root: pathlib.Path = ROOT):
    """Return (status, html). status ∈ {filled, placeholder, error}. Never raises."""
    stop = _STOP_BY_KEY[key]
    data = load_json(root, stop.get("data"))
    kicker = f"showcase · stop {stop['num']:02d}"
    try:
        if data is None and stop.get("data") is not None:
            body = r.pending(stop["title"], stop["needs"] or "provide the data file")
            return "placeholder", r.document(stop["title"], kicker, stop["title"], stop["cue"], body)
        return "filled", render_filled(data, root, stop)
    except Exception as e:  # a broken generator must not break the walk — record it, still serve a page
        body = r.pending(stop["title"], stop["needs"] or "", why=f"generator error: {type(e).__name__}: {e}")
        return "error", r.document(stop["title"], kicker, stop["title"], stop["cue"], body)


def write(key: str, render_filled, root: pathlib.Path = ROOT) -> str:
    """Build and write presentation/<out>.html. Returns the status."""
    stop = _STOP_BY_KEY[key]
    status, html = build(key, render_filled, root)
    (root / "presentation" / stop["out"]).write_text(html)
    return status


def cli(key: str, render_filled):
    status = write(key, render_filled)
    stop = _STOP_BY_KEY[key]
    print(f"[build_{key}] wrote presentation/{stop['out']} ({status})")

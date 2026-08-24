"""Orchestrator · `make showcase` — run every stop generator, write the pages, print a COMPLETION MATRIX.

The matrix is the honesty surface (J-02): per stop it shows FILLED (rendered from real data),
PLACEHOLDER (no domain data yet — shows a house-style "pending: run X" card, not a fake or a 404), or
ERROR (a generator raised — the page still serves a clean placeholder). On a fresh domain repo you fill the
data files (see docs/SHOWCASE-DATA.md) and re-run — you never hand-write HTML.

Run: python -m presentation.build_all
"""
from __future__ import annotations

import importlib
import pathlib

from presentation.tokens import STOPS

ROOT = pathlib.Path(__file__).resolve().parent.parent

# generated stops (out != None) map to a build_<key> module; hub is generated separately; chat/dashboard
# are served from api/*.html (the frame's own pages), shown in the matrix as "static (frame)".
_GENERATED = [s for s in STOPS if s.get("out")]


def run(root: pathlib.Path = ROOT):
    results = []

    # the hub (index of all stops)
    from presentation import build_hub
    build_hub.write(root)
    results.append(("hub", "/hub", "index-hub.html", "filled"))

    for s in _GENERATED:
        mod = importlib.import_module(f"presentation.build_{s['key']}")
        status, html = mod.build(root)
        (root / "presentation" / s["out"]).write_text(html)
        results.append((s["key"], s["route"], s["out"], status))

    # frame-served stops (not generated here)
    for s in STOPS:
        if not s.get("out"):
            results.append((s["key"], s["route"], f"api/{'chat' if s['key']=='chat' else 'dashboard'}.html", "static (frame)"))

    _print_matrix(results)
    return results


_ICON = {"filled": "✓ filled", "placeholder": "◦ placeholder", "error": "✗ error", "static (frame)": "· static"}


def _print_matrix(results):
    order = {s["route"]: s["num"] for s in STOPS}
    order["/hub"] = 0
    results = sorted(results, key=lambda x: order.get(x[1], 99))
    filled = sum(1 for *_, st in results if st == "filled")
    ph = sum(1 for *_, st in results if st == "placeholder")
    err = sum(1 for *_, st in results if st == "error")
    print("\n=== SHOWCASE COMPLETION MATRIX ===")
    print(f"{'stop':<12}{'route':<12}{'status':<16}file")
    print("-" * 60)
    for key, route, out, status in results:
        print(f"{key:<12}{route:<12}{_ICON.get(status, status):<16}presentation/{out}" if not out.startswith("api/")
              else f"{key:<12}{route:<12}{_ICON.get(status, status):<16}{out}")
    print("-" * 60)
    print(f"{filled} filled · {ph} placeholder (pending domain data) · {err} error · "
          f"{len(results)-filled-ph-err} static")
    print("Placeholders are honest, not broken: each shows the exact step to fill it (see docs/SHOWCASE-DATA.md).")


if __name__ == "__main__":
    run()

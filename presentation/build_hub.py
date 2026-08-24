"""Generator · /hub — the index of all 12 stops, rendered from the STOPS registry (one source). Links are
RELATIVE (host/port-agnostic). Always "filled" — it's structural, not data-driven.
Run: python -m presentation.build_hub
"""
from presentation import _base
from presentation import render as r
from presentation.tokens import HOUSE_CSS, STOPS

KEY = "hub"


def render_html():
    rows = ""
    for s in STOPS:
        rows += (
            f'<a class="stoprow" href="{r.esc(s["route"])}">'
            f'<span class="sn">{s["num"]}</span>'
            f'<span class="st"><b>{r.esc(s["title"])}</b><span class="sd">{r.esc(s["cue"])}</span></span>'
            f'<span class="sr">{r.esc(s["route"])}</span></a>'
        )
    extra = (
        ".stoprow{display:flex;gap:14px;align-items:center;background:var(--panel);border:1px solid var(--line);"
        "border-radius:12px;padding:13px 16px;margin:9px 0;text-decoration:none;color:inherit;box-shadow:var(--shadow)}"
        ".stoprow:hover{border-color:var(--structure)}"
        ".sn{flex:0 0 32px;height:32px;border-radius:8px;background:#EAF0FA;color:var(--structure);font-weight:800;"
        "font-family:var(--mono);display:flex;align-items:center;justify-content:center}"
        ".st{display:flex;flex-direction:column} .st b{font-weight:700} .sd{color:var(--mut);font-size:12.5px}"
        ".sr{margin-left:auto;font-family:var(--mono);font-size:12px;color:var(--structure);white-space:nowrap}"
    )
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width, initial-scale=1'>"
        "<title>Showcase — the walk</title>"
        f"<style>{HOUSE_CSS}\n{extra}</style></head><body><div class=wrap>"
        "<header><div class=kicker>governed agent · the walk</div>"
        "<h1>The 12-stop showcase</h1>"
        "<div class=sub>Every stop is generated from this repo's real data by <code>make showcase</code>. "
        "Unfilled stops render an honest &ldquo;pending&rdquo; card — never a fake.</div></header>"
        f"{rows}"
        "<div class=foot>Links are relative — the walk works regardless of host/port.</div>"
        "</div></body></html>"
    )


def render_filled(data, root, stop):   # signature match; hub ignores data
    return render_html()


def build(root=_base.ROOT):
    return "filled", render_html()


def write(root=_base.ROOT):
    (root / "presentation" / "index-hub.html").write_text(render_html())
    return "filled"


if __name__ == "__main__":
    write()
    print("[build_hub] wrote presentation/index-hub.html (filled)")

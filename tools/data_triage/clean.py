"""Composable, idempotent, LOGGED cleaning primitives + a run() driver — no hand-cleaning. Streams rows
through a chosen sequence (memory-safe on huge files), writes cleaned output + an ordered clean_log.json
(rows in→out and cells changed per step). Row-dropping primitives (dedup/drop_nulls/drop_malformed/
filter_tenant) reduce rows; transforms (normalize/coerce/redact/strip/fill/split) change cells. Reuses the
agent's redact_pii + injection detector (no duplication).
"""
from __future__ import annotations

import csv
import json
import os
import re

from .profile import DUP_HASH_CAP, _iter_json_objects, detect

_WS = re.compile(r"\s+")
_NUMISH = re.compile(r"^[\s$€£]*[+-]?[\d,]+(\.\d+)?[\s%]*$")
_TENANT_COL = re.compile(r"tenant|org|company|account|customer|client", re.I)


def _agent():
    from agent.guards import injection_score, redact_pii
    return redact_pii, injection_score


# each primitive: fn(row: dict, ctx: dict) -> (row|None, cells_changed)
def _p_normalize_whitespace(row, ctx):
    ch = 0
    for k, v in row.items():
        if isinstance(v, str):
            nv = _WS.sub(" ", v).strip()
            if nv != v: row[k] = nv; ch += 1
    return row, ch

def _p_normalize_case(row, ctx):
    ch = 0
    for k, v in row.items():
        if isinstance(v, str) and v and not _NUMISH.match(v):
            nv = v.casefold()
            if nv != v: row[k] = nv; ch += 1
    return row, ch

def _p_normalize_encoding(row, ctx):
    ch = 0
    for k, v in row.items():
        if isinstance(v, str):
            nv = "".join(c for c in v if c == "\t" or c >= " ").replace("�", "")
            if nv != v: row[k] = nv; ch += 1
    return row, ch

def _p_coerce_types(row, ctx):
    ch = 0
    for k, v in row.items():
        if isinstance(v, str) and _NUMISH.match(v):
            nv = re.sub(r"[\s$€£,%]", "", v)
            if nv != v: row[k] = nv; ch += 1
    return row, ch

def _p_fill_nulls(row, ctx):
    ch = 0; fill = ctx.get("fill", "NA")
    for k, v in row.items():
        if v is None or v == "": row[k] = fill; ch += 1
    return row, ch

def _p_redact_pii(row, ctx):
    redact = ctx["redact"]; ch = 0
    for k, v in row.items():
        if isinstance(v, str) and v:
            nv = redact(v)
            if nv != v: row[k] = nv; ch += 1
    return row, ch

def _p_strip_injection(row, ctx):
    score = ctx["inj"]; ch = 0
    for k, v in row.items():
        if isinstance(v, str) and v and score(v) >= 0.5:
            row[k] = "[REMOVED:injection]"; ch += 1
    return row, ch

def _p_split_compound(row, ctx):
    ch = 0
    for k in list(row.keys()):
        v = row[k]
        if isinstance(v, str) and " | " in v:
            parts = v.split(" | ")
            for i, p in enumerate(parts):
                row[f"{k}_{i+1}"] = p.strip()
            ch += 1
    return row, ch

def _p_dedup(row, ctx):
    key = json.dumps(row, sort_keys=True, default=str)
    seen = ctx.setdefault("_seen", set())
    if key in seen: return None, 0
    if len(seen) < DUP_HASH_CAP: seen.add(key)
    return row, 0

def _p_drop_nulls(row, ctx):
    if any(v is None or v == "" for v in row.values()): return None, 0
    return row, 0

def _p_drop_malformed(row, ctx):
    if ctx.get("_malformed") or row.get("__malformed__"): return None, 0
    return row, 0

def _p_filter_tenant(row, ctx):
    tgt = ctx.get("tenant")
    if not tgt: return row, 0
    for k, v in row.items():
        if _TENANT_COL.search(k):
            return (row, 0) if str(v).strip().casefold() == tgt.casefold() else (None, 0)
    return row, 0


PRIMS = {
    "normalize_whitespace": _p_normalize_whitespace, "normalize_case": _p_normalize_case,
    "normalize_encoding": _p_normalize_encoding, "coerce_types": _p_coerce_types,
    "fill_nulls": _p_fill_nulls, "redact_pii": _p_redact_pii, "strip_injection": _p_strip_injection,
    "split_compound": _p_split_compound, "dedup": _p_dedup, "drop_nulls": _p_drop_nulls,
    "drop_malformed": _p_drop_malformed, "filter_tenant": _p_filter_tenant,
}
DEFAULT_RECIPE = ["drop_malformed", "normalize_encoding", "normalize_whitespace",
                  "strip_injection", "redact_pii", "dedup"]


def _read_rows(path):
    enc, fmt, delim = detect(path)
    if fmt in ("csv", "tsv"):
        with open(path, encoding=enc, errors="replace", newline="") as f:
            reader = csv.reader(f, delimiter=delim)
            header = [h.strip() for h in next(reader)]
            for raw in reader:
                malformed = len(raw) != len(header)
                yield {header[i]: (raw[i] if i < len(raw) else None) for i in range(len(header))}, header, fmt, malformed
    elif fmt in ("json", "jsonl"):
        for rec in _iter_json_objects(path, enc):
            yield (rec if isinstance(rec, dict) else {"value": rec}), None, "jsonl", (isinstance(rec, dict) and "__malformed__" in rec)
    else:
        with open(path, encoding=enc, errors="replace") as f:
            for line in f:
                yield {"line": line.rstrip("\n")}, ["line"], "txt", False


def run(path: str, recipe=None, out_path: str | None = None) -> dict:
    """Apply the recipe streaming; write cleaned output; return the ordered change-log."""
    recipe = recipe or DEFAULT_RECIPE
    steps = [s for s in recipe if s in PRIMS]
    redact, inj = _agent()
    ctx = {"redact": redact, "inj": inj, "fill": "NA", "tenant": (out_path and None)}
    log = [{"step": s, "rows_in": 0, "rows_out": 0, "dropped": 0, "cells_changed": 0} for s in steps]
    rows_in = rows_out = 0
    out_fmt = None; writer = None; out_f = None; out_header = None
    out_path = out_path or (os.path.splitext(path)[0] + ".cleaned")

    def _emit(row):
        nonlocal writer, out_f, out_header, out_fmt
        if out_fmt in ("csv", "tsv", "txt"):
            if writer is None:
                out_header = list(row.keys())
                out_f = open(out_path, "w", newline="", encoding="utf-8")
                writer = csv.DictWriter(out_f, fieldnames=out_header, extrasaction="ignore")
                writer.writeheader()
            writer.writerow(row)
        else:
            if out_f is None: out_f = open(out_path, "w", encoding="utf-8")
            out_f.write(json.dumps(row, default=str) + "\n")

    for row, header, fmt, malformed in _read_rows(path):
        out_fmt = "csv" if fmt in ("csv", "tsv", "txt") else "jsonl"
        rows_in += 1
        ctx["ncols"] = len(header) if header else None
        ctx["_malformed"] = malformed
        alive = row
        for i, s in enumerate(steps):
            log[i]["rows_in"] += 1
            res, changed = PRIMS[s](alive, ctx)
            log[i]["cells_changed"] += changed
            if res is None:
                log[i]["dropped"] += 1; alive = None; break
            log[i]["rows_out"] += 1; alive = res
        if alive is not None:
            _emit(alive); rows_out += 1
    if out_f: out_f.close()

    return {"file": os.path.basename(path), "recipe": steps, "out_path": os.path.basename(out_path),
            "rows_in": rows_in, "rows_out": rows_out, "steps": log}

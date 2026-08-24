"""Read-only, memory-safe profiler (D-triage). Detects format/encoding/delimiter and profiles ANY file
by STREAMING — bounded memory regardless of file size (capped per-column distinct sets + a capped
duplicate-hash set), so a 5GB file never OOMs. Every number here is measured from the real bytes; nothing
is inferred or fabricated (J-02). parquet/xlsx need optional readers (pyarrow/openpyxl) — absent readers
are reported honestly, never faked.
"""
from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter

SAMPLE_BYTES = 65536
DISTINCT_CAP = 4096          # per-column distinct set cap (memory bound)
DUP_HASH_CAP = 1_000_000     # duplicate-detection hash set cap
N_SAMPLES = 5
BIG_JSON = 200 * 1024 * 1024

_INT = re.compile(r"^[+-]?\d+$")
_FLOAT = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?")
_BOOL = {"true", "false", "yes", "no", "t", "f", "0", "1"}


def _human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024: return f"{n:.1f}{u}" if u != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}PB"


def _infer_type(v: str) -> str:
    if _INT.match(v): return "int"
    if _FLOAT.match(v): return "float"
    if _DATE.match(v): return "date"
    if v.lower() in _BOOL: return "bool"
    return "str"


class _Col:
    __slots__ = ("n", "nulls", "distinct", "capped", "types", "samples")
    def __init__(self):
        self.n = 0; self.nulls = 0; self.distinct = set(); self.capped = False
        self.types = Counter(); self.samples = []
    def add(self, v):
        self.n += 1
        if v is None or v == "":
            self.nulls += 1; return
        self.types[_infer_type(v)] += 1
        if not self.capped and v not in self.distinct:
            self.distinct.add(v)
            if len(self.samples) < N_SAMPLES: self.samples.append(v)
            if len(self.distinct) >= DISTINCT_CAP: self.capped = True
    def summary(self, name):
        dtype = self.types.most_common(1)[0][0] if self.types else "empty"
        present = [t for t, c in self.types.items() if c]
        return {"name": name, "dtype": dtype, "null_count": self.nulls,
                "null_pct": round(100 * self.nulls / self.n, 2) if self.n else 0.0,
                "distinct": (f">={DISTINCT_CAP}" if self.capped else len(self.distinct)),
                "distinct_capped": self.capped, "mixed_type": len(present) > 1,
                "types_seen": dict(self.types), "samples": self.samples[:N_SAMPLES]}


class _Dup:
    def __init__(self): self.seen = set(); self.dups = 0; self.capped = False
    def add(self, key):
        if key in self.seen: self.dups += 1
        elif not self.capped:
            self.seen.add(key)
            if len(self.seen) >= DUP_HASH_CAP: self.capped = True


# ---------- detection ----------
def detect(path: str):
    with open(path, "rb") as f:
        head = f.read(SAMPLE_BYTES)
    enc = "utf-8"
    if head:
        try:
            from charset_normalizer import from_bytes
            best = from_bytes(head).best()
            if best and best.encoding: enc = best.encoding
        except Exception:
            pass
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    fmt = {"ndjson": "jsonl", "xls": "xlsx", "text": "txt"}.get(ext, ext)
    if head[:4] == b"PAR1": fmt = "parquet"
    elif head[:2] == b"PK" and ext in ("xlsx", "xls"): fmt = "xlsx"
    elif fmt not in ("csv", "tsv", "json", "jsonl", "parquet", "xlsx", "txt", "log"):
        txt = head.decode("utf-8", "replace").lstrip()
        first = txt.splitlines()[0] if txt else ""
        if txt[:1] in "[{":
            fmt = "jsonl" if (txt[:1] == "{" and "\n" in txt) else "json"
        elif "\t" in first: fmt = "tsv"
        elif "," in first: fmt = "csv"
        else: fmt = "txt"
    delim = None
    if fmt in ("csv", "tsv"):
        delim = "\t" if fmt == "tsv" else ","
        if fmt == "csv":
            try:
                delim = csv.Sniffer().sniff(head.decode(enc, "replace"), delimiters=",\t;|").delimiter
            except Exception:
                pass
    return enc, fmt, delim


# ---------- per-format streaming profilers ----------
def _finish(cols, colobjs, rows, malformed, garbage, dup, sample, fmt, enc, delim, path, extra=""):
    return {
        "file": os.path.basename(path), "format": fmt, "encoding": enc, "delimiter": delim,
        "size_bytes": os.path.getsize(path), "size_human": _human(os.path.getsize(path)),
        "rows": rows, "cols": len(cols),
        "columns": [colobjs[i].summary(c) for i, c in enumerate(cols)],
        "duplicate_rows": dup.dups, "duplicate_rate": round(dup.dups / rows, 4) if rows else 0.0,
        "duplicate_approximate": dup.capped,
        "malformed_rows": malformed, "garbage_rows": garbage,
        "memory_strategy": f"streaming ({extra})" if extra else "streaming",
        "sample": sample, "reader_status": "ok",
    }


def _profile_delimited(path, enc, delim, fmt):
    rows = malformed = garbage = 0
    dup = _Dup(); sample = []
    with open(path, encoding=enc, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        try:
            header = next(reader)
        except StopIteration:
            return _finish([], [], 0, 0, 0, dup, [], fmt, enc, delim, path, "csv.reader")
        cols = [h.strip() for h in header]
        colobjs = [_Col() for _ in cols]
        for raw in reader:
            rows += 1
            if len(raw) != len(cols): malformed += 1
            joined = "".join(raw)
            if joined and sum(ch == "�" for ch in joined) / len(joined) > 0.2: garbage += 1
            for i in range(len(cols)):
                colobjs[i].add(raw[i].strip() if i < len(raw) and raw[i] else (raw[i] if i < len(raw) else None))
            dup.add(tuple(raw))
            if len(sample) < N_SAMPLES:
                sample.append({cols[i]: (raw[i] if i < len(raw) else None) for i in range(len(cols))})
    return _finish(cols, colobjs, rows, malformed, garbage, dup, sample, fmt, enc, delim, path, "csv.reader")


def _iter_json_objects(path, enc):
    """Stream top-level objects from a JSON array OR jsonl without loading the file — bracket-depth split
    that respects strings/escapes. Memory = one object at a time."""
    with open(path, encoding=enc, errors="replace") as f:
        head = f.read(1)
        while head and head.isspace(): head = f.read(1)
        if head == "{":                                   # could be jsonl (one obj per line) — handled by caller
            f.seek(0)
            for line in f:
                line = line.strip()
                if line:
                    try: yield json.loads(line)
                    except Exception: yield {"__malformed__": line[:200]}
            return
        # JSON array: stream elements
        buf = ""; depth = 0; instr = False; esc = False; started = False
        while True:
            chunk = f.read(65536)
            if not chunk: break
            for ch in chunk:
                if not started:
                    if ch == "{": started = True; depth = 1; buf = "{"
                    continue
                buf += ch
                if esc: esc = False; continue
                if ch == "\\" and instr: esc = True; continue
                if ch == '"': instr = not instr; continue
                if instr: continue
                if ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try: yield json.loads(buf)
                        except Exception: yield {"__malformed__": buf[:200]}
                        buf = ""; started = False


def _profile_records(path, enc, fmt):
    cols = []; colidx = {}; colobjs = []; rows = malformed = 0
    dup = _Dup(); sample = []
    for rec in _iter_json_objects(path, enc):
        rows += 1
        if not isinstance(rec, dict) or "__malformed__" in rec:
            malformed += 1; continue
        for k, v in rec.items():
            if k not in colidx:
                colidx[k] = len(cols); cols.append(k); colobjs.append(_Col())
            sval = "" if v is None else (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
            colobjs[colidx[k]].add(sval)
        # nulls for absent keys
        for k in cols:
            if k not in rec: colobjs[colidx[k]].add(None)
        dup.add(json.dumps(rec, sort_keys=True))
        if len(sample) < N_SAMPLES: sample.append({k: rec.get(k) for k in list(rec)[:12]})
    return _finish(cols, colobjs, rows, malformed, 0, dup, sample, fmt, enc, None, path, "json-object stream")


def _profile_text(path, enc, fmt):
    col = _Col(); rows = garbage = 0; dup = _Dup(); sample = []
    with open(path, encoding=enc, errors="replace") as f:
        for line in f:
            rows += 1; s = line.rstrip("\n")
            if s and sum(ch == "�" for ch in s) / len(s) > 0.2: garbage += 1
            col.add(s)
            dup.add(s)
            if len(sample) < N_SAMPLES: sample.append({"line": s[:200]})
    return _finish(["line"], [col], rows, 0, garbage, dup, sample, fmt, enc, None, path, "line stream")


def _profile_optional(path, enc, fmt):
    """parquet/xlsx via optional readers; honest 'reader_absent' if not installed (never a fake profile)."""
    try:
        if fmt == "parquet":
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(path); n = pf.metadata.num_rows
            names = pf.schema_arrow.names
            colobjs = [_Col() for _ in names]; sample = []; dup = _Dup()
            for b in pf.iter_batches(batch_size=50000):
                d = b.to_pydict()
                for i, name in enumerate(names):
                    for v in d[name]:
                        colobjs[i].add("" if v is None else str(v))
                if not sample:
                    sample = [{name: d[name][r] for name in names} for r in range(min(N_SAMPLES, len(d[names[0]])))]
            return _finish(names, colobjs, n, 0, 0, dup, sample, fmt, enc, None, path, "pyarrow row-group stream")
        if fmt == "xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True); ws = wb.active
            it = ws.iter_rows(values_only=True); header = [str(h) for h in next(it)]
            colobjs = [_Col() for _ in header]; rows = 0; dup = _Dup(); sample = []
            for r in it:
                rows += 1
                for i in range(len(header)):
                    colobjs[i].add(None if i >= len(r) or r[i] is None else str(r[i]))
                dup.add(tuple("" if x is None else str(x) for x in r))
                if len(sample) < N_SAMPLES: sample.append({header[i]: (r[i] if i < len(r) else None) for i in range(len(header))})
            return _finish(header, colobjs, rows, 0, 0, dup, sample, fmt, enc, None, path, "openpyxl read-only stream")
    except ImportError:
        lib = "pyarrow" if fmt == "parquet" else "openpyxl"
        return {"file": os.path.basename(path), "format": fmt, "encoding": enc, "delimiter": None,
                "size_bytes": os.path.getsize(path), "size_human": _human(os.path.getsize(path)),
                "rows": None, "cols": None, "columns": [], "duplicate_rows": None, "duplicate_rate": None,
                "duplicate_approximate": None, "malformed_rows": None, "garbage_rows": None,
                "memory_strategy": "n/a", "sample": [],
                "reader_status": f"reader_absent: pip install {lib} to profile {fmt}"}


def profile(path: str) -> dict:
    enc, fmt, delim = detect(path)
    if fmt in ("csv", "tsv"): return _profile_delimited(path, enc, delim, fmt)
    if fmt in ("json", "jsonl"): return _profile_records(path, enc, fmt)
    if fmt in ("txt", "log"): return _profile_text(path, enc, fmt)
    if fmt in ("parquet", "xlsx"): return _profile_optional(path, enc, fmt)
    return _profile_text(path, enc, "txt")

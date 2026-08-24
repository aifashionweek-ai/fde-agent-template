"""Trust-boundary scan (the architect layer). Screens a dataset the way retrieval screens its corpus —
because this data MAY become the agent's retrieval surface. Reuses the governed agent's OWN detectors
(agent.guards PII + injection) rather than duplicating them (ties to D-043); does not modify the core.

Streams up to SCAN_ROW_CAP rows (bounded), so it stays memory-safe on huge files. Every count is measured;
examples are PII-redacted. findings.json rows: {finding, severity, column, count, examples, confidence}.
"""
from __future__ import annotations
import csv, json, os, re

from .profile import detect, _iter_json_objects

SCAN_ROW_CAP = 500_000
EX = 3

_TENANT_COL = re.compile(r"tenant|org|organi[sz]ation|company|account|customer|client", re.I)
_NAME_COL = re.compile(r"\b(name|first|last|full[_ ]?name|employee|customer|contact)\b", re.I)


def _detectors():
    """Reuse the agent's real detectors (no duplication, ties to D-043)."""
    from agent.guards import _PII, injection_score, redact_pii
    return _PII, injection_score, redact_pii


def _rows(path):
    """Yield (rowdict) up to the cap; works for delimited / json / text via the profiler's detect + streamers."""
    enc, fmt, delim = detect(path)
    n = 0
    if fmt in ("csv", "tsv"):
        with open(path, encoding=enc, errors="replace", newline="") as f:
            reader = csv.reader(f, delimiter=delim)
            try: header = [h.strip() for h in next(reader)]
            except StopIteration: return
            for raw in reader:
                yield {header[i]: (raw[i] if i < len(raw) else "") for i in range(len(header))}
                n += 1
                if n >= SCAN_ROW_CAP: return
    elif fmt in ("json", "jsonl"):
        for rec in _iter_json_objects(path, enc):
            if isinstance(rec, dict):
                yield {k: ("" if v is None else v if isinstance(v, str) else json.dumps(v)) for k, v in rec.items()}
            n += 1
            if n >= SCAN_ROW_CAP: return
    else:
        with open(path, encoding=enc, errors="replace") as f:
            for line in f:
                yield {"line": line.rstrip("\n")}
                n += 1
                if n >= SCAN_ROW_CAP: return


def scan(path: str) -> dict:
    _PII, injection_score, redact_pii = _detectors()
    pii = {}          # (label, column) -> {count, examples}
    inj = {}          # column -> {count, examples}
    name_cols = set()
    tenant_vals = {}  # column -> set of distinct values (capped)
    scanned = 0; truncated = False

    for row in _rows(path):
        scanned += 1
        for col, v in row.items():
            if not isinstance(v, str) or not v:
                continue
            if _NAME_COL.search(col):
                name_cols.add(col)
            if _TENANT_COL.search(col):
                s = tenant_vals.setdefault(col, set())
                if len(s) < 64: s.add(v[:64])
            for rx, label in _PII:
                if rx.search(v):
                    d = pii.setdefault((label, col), {"count": 0, "examples": []})
                    d["count"] += 1
                    if len(d["examples"]) < EX: d["examples"].append(redact_pii(v)[:120])
            if injection_score(v) >= 0.5:
                d = inj.setdefault(col, {"count": 0, "examples": []})
                d["count"] += 1
                if len(d["examples"]) < EX: d["examples"].append(redact_pii(v)[:160])
        if scanned >= SCAN_ROW_CAP:
            truncated = True; break

    findings = []
    for (label, col), d in sorted(pii.items(), key=lambda x: -x[1]["count"]):
        sev = "high" if label.strip("[]") in ("SSN", "CARD") else "medium"
        findings.append({"finding": f"PII {label} in column '{col}'", "severity": sev, "column": col,
                         "count": d["count"], "examples": d["examples"], "confidence": "hit"})
    for col, d in sorted(inj.items(), key=lambda x: -x[1]["count"]):
        findings.append({"finding": f"prompt-injection / embedded-instruction text in column '{col}'",
                         "severity": "high", "column": col, "count": d["count"],
                         "examples": d["examples"], "confidence": "hit",
                         "note": "retrieved content is UNTRUSTED — data, not instructions (D-043)"})
    for col in sorted(name_cols):
        findings.append({"finding": f"likely personal names in column '{col}' (column-name heuristic)",
                         "severity": "medium", "column": col, "count": None,
                         "examples": [], "confidence": "heuristic"})
    for col, vals in tenant_vals.items():
        if len(vals) > 1:
            findings.append({"finding": f"multiple tenants/orgs mixed in column '{col}'", "severity": "high",
                             "column": col, "count": len(vals), "examples": sorted(vals)[:8],
                             "confidence": "heuristic",
                             "note": "if this becomes the retrieval corpus, isolate per tenant BEFORE indexing (D-011)"})

    return {"file": os.path.basename(path), "rows_scanned": scanned, "truncated": truncated,
            "scan_cap": SCAN_ROW_CAP, "findings": findings,
            "summary": {"pii_columns": len({c for _, c in pii}), "injection_columns": len(inj),
                        "tenant_mixed": any(len(v) > 1 for v in tenant_vals.values()),
                        "total_findings": len(findings)}}

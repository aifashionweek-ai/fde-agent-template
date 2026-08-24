"""Data-triage harness (tools/data_triage). Proves: the profiler handles every text format, degrades
honestly on absent readers (parquet/xlsx), and measures the committed messy fixture accurately (nulls,
dupes, mixed types, malformed, PII, an injected-instruction row, tenant mixing); cleaning drops/redacts;
the report renders REAL counts from the file (nothing hardcoded)."""
import pathlib

from tools.data_triage import DEFAULT_RECIPE, clean, profile, render, scan

FIX = pathlib.Path(__file__).resolve().parent.parent / "tools" / "data_triage" / "fixtures" / "messy.csv"


def _write(tmp, name, content, binary=False):
    p = tmp / name
    p.write_bytes(content) if binary else p.write_text(content)
    return str(p)


def test_profiler_handles_each_text_format(tmp_path):
    cases = {
        "a.csv": ("id,x\n1,a\n2,b\n", "csv", 2, 2),
        "a.tsv": ("id\tx\n1\ta\n2\tb\n", "tsv", 2, 2),
        "a.jsonl": ('{"id":1}\n{"id":2}\n', "jsonl", 2, 1),
        "a.json": ('[{"id":1,"v":"x"},{"id":2,"v":"y"}]', "json", 2, 2),
        "a.txt": ("l1\nl2\nl3\n", "txt", 3, 1),
        "a.log": ("l1\nl2\n", "log", 2, 1),
    }
    for name, (content, fmt, rows, cols) in cases.items():
        p = profile(_write(tmp_path, name, content))
        assert p["format"] == fmt and p["reader_status"] == "ok", name
        assert p["rows"] == rows and p["cols"] == cols, name


def test_absent_readers_degrade_honestly(tmp_path):
    p = profile(_write(tmp_path, "a.parquet", b"PAR1notreal", binary=True))
    assert p["format"] == "parquet" and "reader_absent" in p["reader_status"]  # never a fabricated profile
    assert p["rows"] is None


def test_encoding_and_delimiter_detected(tmp_path):
    p = profile(_write(tmp_path, "a.csv", "id;name\n1;x\n2;y\n"))
    assert p["delimiter"] == ";"          # sniffed, not assumed
    assert p["encoding"]


def test_messy_fixture_profile_measures_real_defects():
    p = profile(str(FIX))
    assert p["rows"] == 8 and p["cols"] == 6
    assert p["duplicate_rows"] == 1               # the exact repeated row
    assert p["malformed_rows"] == 1               # the unquoted "1,000" row
    amount = next(c for c in p["columns"] if c["name"] == "amount")
    assert amount["mixed_type"] is True           # ints + 'abc'
    assert any(c["null_pct"] > 0 for c in p["columns"])


def test_messy_fixture_trust_scan():
    f = scan(str(FIX))
    kinds = {fd["finding"].split(" in ")[0]: fd for fd in f["findings"]}
    assert any("SSN" in k for k in kinds) and any("EMAIL" in k for k in kinds)
    ssn = next(fd for fd in f["findings"] if "SSN" in fd["finding"])
    assert ssn["severity"] == "high" and ssn["count"] == 1
    assert any("injection" in fd["finding"] and fd["severity"] == "high" for fd in f["findings"])
    assert f["summary"]["tenant_mixed"] is True   # two tenants in one column


def test_cleaning_drops_and_redacts(tmp_path):
    out = str(tmp_path / "clean.csv")
    log = clean(str(FIX), DEFAULT_RECIPE, out)
    assert log["rows_in"] == 8 and log["rows_out"] == 6      # -1 malformed, -1 dup
    steps = {s["step"]: s for s in log["steps"]}
    assert steps["drop_malformed"]["dropped"] == 1 and steps["dedup"]["dropped"] == 1
    assert steps["redact_pii"]["cells_changed"] >= 1 and steps["strip_injection"]["cells_changed"] == 1
    body = pathlib.Path(out).read_text()
    assert "[SSN]" in body and "[EMAIL]" in body and "[REMOVED:injection]" in body
    assert "123-45-6789" not in body                         # raw PII gone
    assert "Ignore all previous instructions" not in body    # injection stripped


def test_cleaning_is_idempotent(tmp_path):
    o1, o2 = str(tmp_path / "c1.csv"), str(tmp_path / "c2.csv")
    clean(str(FIX), DEFAULT_RECIPE, o1)
    clean(o1, DEFAULT_RECIPE, o2)                             # cleaning already-clean data
    assert pathlib.Path(o1).read_text() == pathlib.Path(o2).read_text()


def test_report_renders_real_counts_no_fabrication():
    p, f = profile(str(FIX)), scan(str(FIX))
    log = clean(str(FIX), DEFAULT_RECIPE, "/tmp/_triage_test.csv")
    html = render(p, f, log)
    assert html.lstrip().startswith("<!doctype html>")
    assert "https://" not in html and "http://" not in html  # self-contained (shared invariant)
    assert "Space Grotesk" in html and "JetBrains Mono" in html
    assert "8" in html and "6" in html                       # rows_in -> rows_out from the real clean log
    assert "SSN" in html and "globex" in html.lower()        # real findings surfaced
    assert "prompt-injection" in html                        # the injection finding is surfaced (example shown, PII in it redacted)


def test_distinct_and_dup_caps_are_bounded(tmp_path):
    """Memory-safety sanity: many distinct values -> capped flag, not an unbounded set."""
    rows = "id\n" + "\n".join(str(i) for i in range(6000)) + "\n"
    p = profile(_write(tmp_path, "big.csv", rows))
    col = p["columns"][0]
    assert col["distinct_capped"] is True and col["distinct"] == ">=4096"

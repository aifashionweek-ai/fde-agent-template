"""CLI: point it at ANY file → profile.json, findings.json, (optional) cleaned output + clean_log.json,
and DATA-REPORT.html. One command, unknown file → report + clean data.

  python -m tools.data_triage <file>                       # profile + scan + report
  python -m tools.data_triage <file> --clean               # + default clean recipe
  python -m tools.data_triage <file> --clean dedup,redact_pii --out cleaned.csv
"""
import argparse, json, os, pathlib, sys

# allow running as `python -m tools.data_triage` from repo root (so `agent.guards` reuse resolves)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.data_triage.profile import profile
from tools.data_triage.scan import scan
from tools.data_triage.clean import run as clean_run, DEFAULT_RECIPE
from tools.data_triage.report import render


def main(argv=None):
    ap = argparse.ArgumentParser(prog="data_triage", description="Profile/scan/clean any file → HTML report.")
    ap.add_argument("file")
    ap.add_argument("--clean", nargs="?", const="default", default=None,
                    help="run cleaning: 'default' or a comma recipe (e.g. dedup,redact_pii,strip_injection)")
    ap.add_argument("--out", default=None, help="cleaned output path")
    ap.add_argument("--report", default=None, help="DATA-REPORT.html path (default: alongside the input)")
    ap.add_argument("--artifacts-dir", default=None, help="where to write profile/findings/clean_log json")
    a = ap.parse_args(argv)

    if not os.path.exists(a.file):
        print(f"no such file: {a.file}"); return 2
    src = pathlib.Path(a.file)
    outdir = pathlib.Path(a.artifacts_dir) if a.artifacts_dir else src.parent
    outdir.mkdir(parents=True, exist_ok=True)
    stem = src.stem

    prof = profile(a.file)
    (outdir / f"{stem}.profile.json").write_text(json.dumps(prof, indent=2, default=str))
    find = scan(a.file)
    (outdir / f"{stem}.findings.json").write_text(json.dumps(find, indent=2, default=str))

    clog = None
    if a.clean is not None:
        recipe = DEFAULT_RECIPE if a.clean == "default" else [s.strip() for s in a.clean.split(",")]
        out_path = a.out or str(outdir / f"{stem}.cleaned{src.suffix or '.csv'}")
        clog = clean_run(a.file, recipe, out_path)
        (outdir / f"{stem}.clean_log.json").write_text(json.dumps(clog, indent=2, default=str))

    report_path = a.report or str(outdir / f"{stem}-DATA-REPORT.html")
    pathlib.Path(report_path).write_text(render(prof, find, clog))

    print(f"format={prof.get('format')} rows={prof.get('rows')} cols={prof.get('cols')} "
          f"dupes={prof.get('duplicate_rows')} malformed={prof.get('malformed_rows')} "
          f"findings={find['summary']['total_findings']}")
    if clog: print(f"cleaned {clog['rows_in']} -> {clog['rows_out']} rows via {','.join(clog['recipe'])} -> {clog['out_path']}")
    print(f"report -> {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

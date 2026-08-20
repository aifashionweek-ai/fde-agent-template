"""D-028 guard: the Loom deliverables exist, the driver is executable, and it runs the 6 beats in order
with the real commands. Catch-proven: reorder/remove a beat or a command and a test goes red."""
import os, re, pathlib

ROOT = pathlib.Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "loom_demo.sh"
DOC = ROOT / "docs" / "LOOM-SCRIPT.md"


def test_both_deliverables_exist():
    assert SCRIPT.exists(), "scripts/loom_demo.sh missing"
    assert DOC.exists(), "docs/LOOM-SCRIPT.md missing"


def test_script_is_executable_with_shebang():
    assert os.access(SCRIPT, os.X_OK), "loom_demo.sh must be chmod +x"
    assert SCRIPT.read_text().startswith("#!"), "loom_demo.sh needs a shebang"


def test_script_runs_beats_in_order():
    s = SCRIPT.read_text()
    beats = ["BEAT (a)", "BEAT (b)", "BEAT (c)", "BEAT (d)", "BEAT (e)", "BEAT (f)"]
    idx = [s.find(b) for b in beats]
    assert all(i != -1 for i in idx), f"missing beat(s): {[b for b, i in zip(beats, idx) if i == -1]}"
    assert idx == sorted(idx), "beats are out of order in the driver"


def test_script_invokes_the_real_commands():
    s = SCRIPT.read_text()
    for needle in ["README.md", "evals.problem_report", "localhost:8080/run",
                   "evals.audit_report", "docs/model-eval-2026-08-19.md",
                   "scripts/verify_new_engagement.py"]:
        assert needle in s, f"driver missing beat command: {needle}"


def test_doc_is_timestamped_and_covers_beats():
    d = DOC.read_text()
    assert "0:00" in d and re.search(r"[34]:\d\d", d), "LOOM-SCRIPT.md must be timestamped to ~4 min"
    for kw in ["make problem", "/run", "make audit", "model-eval", "verify_new_engagement"]:
        assert kw in d, f"LOOM-SCRIPT.md missing beat: {kw}"

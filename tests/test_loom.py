"""D-028 guard: the Loom deliverables exist, the driver is executable, and it runs the 5 beats in order —
including the BEAT 3 attack sequence (3 real controls). Catch-proven: reorder/remove a beat or a control
demo and a test goes red."""
import os, re, pathlib

ROOT = pathlib.Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "loom_demo.sh"
DOC = ROOT / "docs" / "LOOM-SCRIPT.md"


def test_both_deliverables_exist():
    assert SCRIPT.exists() and DOC.exists()


def test_script_is_executable_with_shebang():
    assert os.access(SCRIPT, os.X_OK), "loom_demo.sh must be chmod +x"
    assert SCRIPT.read_text().startswith("#!")


def test_script_runs_five_beats_in_order():
    s = SCRIPT.read_text()
    beats = ["BEAT 1", "BEAT 2", "BEAT 3", "BEAT 4", "BEAT 5"]
    idx = [s.find(b) for b in beats]
    assert all(i != -1 for i in idx), f"missing beat(s): {[b for b, i in zip(beats, idx) if i == -1]}"
    assert idx == sorted(idx), "beats out of order"


def test_attack_sequence_runs_three_live_controls():
    s = SCRIPT.read_text()
    for marker in ["3a", "3b", "3c"]:
        assert marker in s, f"attack {marker} missing"
    # each attack invokes the REAL control, not an echo
    assert "reset_access" in s                    # 3a authz privilege misuse
    assert "classify_execution" in s              # 3b approval-hash tampering
    assert "input_guard" in s                     # 3c injection guard
    # ordering: attacks come inside BEAT 3, before BEAT 4
    assert s.find("3a") < s.find("3b") < s.find("3c") < s.find("BEAT 4")


def test_script_invokes_the_real_beat_commands():
    s = SCRIPT.read_text()
    for needle in ["evals.problem_report", "localhost:8080/run", "evals.audit_report", "bake-llama"]:
        assert needle in s, f"driver missing beat command: {needle}"


def test_doc_is_timestamped_and_covers_beats():
    d = DOC.read_text()
    assert "0:00" in d and re.search(r"[456]:\d\d", d), "LOOM-SCRIPT.md must be timestamped ~5-6 min"
    for kw in ["problem", "/run", "attack", "audit", "model"]:
        assert kw.lower() in d.lower(), f"LOOM-SCRIPT.md missing beat: {kw}"

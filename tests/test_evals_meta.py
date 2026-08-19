"""D-014: confidence instrumentation works and the gate parses MASTERSCHEMA thresholds."""
from evals.scorers import calibration_error, agreement, path_sane, grounded, hitl_respected

def test_ece_perfect_and_bad():
    assert calibration_error([(1.0, 1), (0.0, 0), (1.0, 1)]) == 0.0
    assert calibration_error([(1.0, 0), (1.0, 0)]) > 0.5

def test_agreement():
    assert agreement([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert agreement([1, 1, 0, 0], [0, 0, 1, 1]) == 0.0

def test_path_sane():
    assert path_sane({"trace": {"path": ["guard_input", "plan", "act", "finalize"]}}) == 1
    assert path_sane({"trace": {"path": ["plan", "finalize"]}}) == 0

def test_grounded_id_shape():
    assert grounded({"citations": ["sla#0"]}) == 1 and grounded({"citations": ["http://x"]}) == 0

def test_hitl_respected():
    assert hitl_respected({"answer": "INTERRUPTED", "confidence": 0}, input="delete all records") == 1
    assert hitl_respected({"answer": "done", "confidence": 0.9, "actions": [{"tool": "write_record"}]}, input="delete all records") == 0

def test_gate_parses_thresholds():
    import evals.gate as g
    assert "Factuality" in g.THRESH and g.THRESH["Factuality"][2] >= 0.8
    assert g.THRESH["schema_valid"][0] == "deterministic"

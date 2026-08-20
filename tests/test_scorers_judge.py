"""D-030 guard: the `factual` judge is correctness-focused and CANNOT rank a wrong answer high by
construction (score mapping is monotonic, D→0.0), and citations are surfaced to the judge so a
'cites <runbook>' rubric is satisfied by the citations FIELD, not prose exact-match.

OFFLINE ONLY — no live LLM calls (the gate must not depend on the network, J-09). The live proof that a
correct answer scores high and a wrong answer scores low is reproduced in evals/rescore.py + the session
log; here we lock the invariants that make that outcome structural."""
from evals.scorers import FACTUAL_SCORES, RUBRIC_SCORES, FACTUAL_PROMPT, answer_for_judge


def test_factual_mapping_rewards_correct_penalizes_wrong():
    # A wrong answer graded 'D' scores 0.0; a fully-correct 'A' scores 1.0; strictly monotonic in between.
    assert FACTUAL_SCORES["A"] == 1.0
    assert FACTUAL_SCORES["D"] == 0.0
    assert FACTUAL_SCORES["A"] > FACTUAL_SCORES["B"] > FACTUAL_SCORES["C"] > FACTUAL_SCORES["D"]


def test_rubric_is_binary_pass_fail():
    assert RUBRIC_SCORES == {"A": 1, "B": 0}


def test_factual_prompt_ignores_verbosity_and_flags_contradiction():
    p = FACTUAL_PROMPT.lower()
    # extra correct detail must NOT lower the grade (the superset-penalty bug is prompted against)
    assert "extra" in p and "not lower the grade" in p
    # a contradiction / wrong value must be graded incorrect
    assert "contradict" in p and "wrong" in p


def test_answer_for_judge_surfaces_citations():
    s = answer_for_judge({"answer": "Refunds within 14 days.", "citations": ["refund-policy#0"]})
    assert "Refunds within 14 days." in s and "refund-policy#0" in s
    # no citations -> answer unchanged
    assert answer_for_judge({"answer": "hello", "citations": []}) == "hello"
    assert answer_for_judge({}) == ""

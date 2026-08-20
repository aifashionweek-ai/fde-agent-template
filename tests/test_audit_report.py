"""D-029 guard: the audit report surfaces ALL capabilities as layers (incl. MCP, Vector backend, Infra),
computes the layer count from the list (not hardcoded), and renders the REAL bake-off finding.

NOTE: we never call audit_report.build() here — build() runs a live `pytest tests` subprocess, so calling
it from within the suite would recurse. We test the data/rendering functions that drive the HTML instead."""
import re, pathlib
import evals.audit_report as ar

SRC = (pathlib.Path(ar.__file__)).read_text()


def test_ten_layers_incl_mcp_vector_infra():
    names = {L["id"]: L["name"] for L in ar.LAYERS}
    assert len(ar.LAYERS) == 10, f"expected 10 layers, got {len(ar.LAYERS)}"
    assert "MCP" in names["L8"]
    assert "Vector" in names["L9"]
    assert "Infra" in names["L10"] or "Deploy" in names["L10"]


def test_layer_count_is_computed_not_hardcoded():
    # the rendered header must interpolate len(LAYERS), and no stale 'The 7 layers' literal remains
    assert "The {len(LAYERS)} layers" in SRC
    assert "The 7 layers" not in SRC


def test_bakeoff_parses_real_numbers():
    bo = ar.load_bakeoff()
    assert bo is not None, "bake-off doc missing — headline finding would be invisible"
    assert bo["n_models"] == 3, bo["models"]
    assert bo["n_scorers"] == 9
    assert bo["all_ones"] is True                 # deterministic scorers 1.00 across all three models
    assert any("qwen" in m.lower() for m in bo["models"])
    assert any("llama" in m.lower() for m in bo["models"])
    assert any("claude" in m.lower() for m in bo["models"])


def test_bakeoff_table_renders_numbers_and_verdict():
    html = ar.bakeoff_table(ar.load_bakeoff())
    assert "1.00" in html
    assert "across ALL 3 models" in html
    assert "schema_valid" in html


def test_bakeoff_table_is_honest_when_data_missing():
    # J-02: no data -> say so, never fabricate
    html = ar.bakeoff_table(None)
    assert "No bake-off data" in html and "1.00" not in html


def test_structural_layer_facts_are_all_green_on_this_repo():
    # L8 MCP, L9 Vector, L10 Infra each expose a live facts() — on a clean repo every check passes
    for lid in ("L8", "L9", "L10"):
        L = next(x for x in ar.LAYERS if x["id"] == lid)
        facts = L["facts"]()
        assert facts, f"{lid} produced no facts"
        assert all(ok for _, _, ok in facts), f"{lid} has a failing fact: {facts}"


def test_mcp_facts_show_4_read_5_withheld():
    L8 = next(x for x in ar.LAYERS if x["id"] == "L8")
    labels = {l: v for l, v, _ in L8["facts"]()}
    assert any("4:" in v for l, v in labels.items() if "READ" in l)
    assert any("5:" in v for l, v in labels.items() if "withheld" in l)

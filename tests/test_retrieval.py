"""D-010 provenance, D-011 routing (tenant + sensitivity + source allow-list). Catch-proven."""
from agent.retrieval import InMemoryIndex, chunk_document, seed_demo, INDEX

def _idx():
    seed_demo(); return INDEX

def test_provenance_on_every_chunk():                    # D-010
    cs = chunk_document("d1", "A sentence. Another one. " * 80, source="s", tenant="t", sensitivity="internal")
    assert len(cs) > 1 and all(c.doc_id == "d1" and c.tenant == "t" and c.source == "s" and c.ingested_at > 0 for c in cs)
    assert all(c.chunk_id == f"d1#{i}" for i, c in enumerate(cs))

def test_tenant_isolation_is_structural():               # D-011
    hits = _idx().search("rotate keys", tenant="demo", max_sensitivity="restricted", k=10)
    assert all(h["doc_id"] != "other-tenant" for h in hits)            # acme content never leaks into demo
    assert any(h["doc_id"] == "other-tenant" for h in _idx().search("rotate keys", tenant="acme", k=10))

def test_sensitivity_ceiling():                          # D-011
    assert all(h["doc_id"] != "secret-pricing" for h in _idx().search("discount floor", tenant="demo", max_sensitivity="internal"))
    assert any(h["doc_id"] == "secret-pricing" for h in _idx().search("discount floor", tenant="demo", max_sensitivity="confidential"))

def test_source_allowlist():                             # D-011
    hits = _idx().search("refund", tenant="demo", max_sensitivity="internal", sources={"contracts"})
    assert all(h["source"] == "contracts" for h in hits)

def test_bm25_ranks_relevant_first():
    hits = _idx().search("refund policy digital goods", tenant="demo", max_sensitivity="public")
    assert hits and hits[0]["doc_id"] == "refund-policy"

def test_unknown_sensitivity_rejected():
    import pytest
    with pytest.raises(AssertionError): chunk_document("x", "t", source="s", tenant="t", sensitivity="topsecret")

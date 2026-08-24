"""D-010/D-011 frame guards: retrieval carries provenance and is ROUTED (tenant isolation + sensitivity
ceiling) BEFORE scoring. Generic corpus (agent.retrieval.seed_demo) — domain-independent."""
from agent.retrieval import InMemoryIndex, chunk_document, seed_demo, INDEX


def _idx():
    seed_demo(); return INDEX


def test_provenance_on_every_chunk():                    # D-010
    c = chunk_document("d", "hello world.", source="s", tenant="demo", sensitivity="internal")[0]
    assert c.doc_id and c.chunk_id and c.source and c.tenant and c.sensitivity


def test_tenant_isolation_is_structural():               # D-011
    idx = InMemoryIndex()
    idx.add(chunk_document("a", "other tenant secret", source="s", tenant="other", sensitivity="internal"))
    idx.add(chunk_document("b", "demo tenant entry", source="s", tenant="demo", sensitivity="internal"))
    hits = idx.search("secret entry", tenant="demo", k=10)
    assert hits and all(h["doc_id"] != "a" for h in hits)   # 'other' tenant never crosses over


def test_sensitivity_ceiling():                          # D-011
    idx = InMemoryIndex()
    idx.add(chunk_document("s", "confidential terms", source="s", tenant="demo", sensitivity="confidential"))
    idx.add(chunk_document("p", "public schedule", source="s", tenant="demo", sensitivity="public"))
    hits = idx.search("terms schedule", tenant="demo", max_sensitivity="internal", k=10)
    assert hits and all(h["sensitivity"] != "confidential" for h in hits)


def test_seed_demo_is_generic_and_tenant_scoped():
    hits = _idx().search("knowledge base entry", tenant="demo", max_sensitivity="internal", k=10)
    assert hits and all(h["doc_id"] != "other-tenant" for h in hits)   # other tenant's doc never surfaces

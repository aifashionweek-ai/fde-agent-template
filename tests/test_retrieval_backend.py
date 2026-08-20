"""D-024 guard: VECTOR_BACKEND switches the retrieval backend behind an UNCHANGED search() contract.
Pinecone is MOCKED — no account, no network, `pinecone` need not be installed. Catch-proof: break the
backend switch, the tenant->namespace mapping, or the sensitivity filter and one of these fails."""
import sys, types, inspect
import pytest
import agent.retrieval as r


def _install_fake_pinecone(monkeypatch, captured):
    """Inject a fake `pinecone` module so PineconeIndex._client() succeeds without the real SDK."""
    fake = types.ModuleType("pinecone")

    class FakeIndex:
        def upsert(self, vectors, namespace=None):
            captured.setdefault("upserts", []).append((namespace, vectors))

        def query(self, *, vector, top_k, namespace, filter, include_metadata):
            captured["query"] = dict(top_k=top_k, namespace=namespace, filter=filter)

            class M:  # modern SDK match shape: object with .id/.score/.metadata
                id = "policy#0"; score = 0.99
                metadata = {"chunk_id": "policy#0", "doc_id": "policy", "text": "reset steps",
                            "source": "policies", "sensitivity": "internal"}

            class R:
                matches = [M()]
            return R()

    class Pinecone:
        def __init__(self, api_key=None): pass
        def Index(self, name):
            captured["index_name"] = name
            return FakeIndex()

    fake.Pinecone = Pinecone
    monkeypatch.setitem(sys.modules, "pinecone", fake)


def test_memory_is_default(monkeypatch):
    monkeypatch.delenv("VECTOR_BACKEND", raising=False)
    assert type(r.make_index()).__name__ == "InMemoryIndex"


def test_pinecone_backend_selected(monkeypatch):
    monkeypatch.setenv("VECTOR_BACKEND", "pinecone")
    assert type(r.make_index()).__name__ == "PineconeIndex"


def test_unknown_backend_is_loud(monkeypatch):
    monkeypatch.setenv("VECTOR_BACKEND", "cosmos")
    with pytest.raises(ValueError):
        r.make_index()


def test_search_contract_signature_is_identical():
    """Both backends expose the same search() signature — callers never branch on backend (contract unchanged)."""
    a = inspect.signature(r.InMemoryIndex.search)
    b = inspect.signature(r.PineconeIndex.search)
    assert list(a.parameters) == list(b.parameters)


def test_pinecone_search_routes_through_client(monkeypatch):
    captured = {}
    _install_fake_pinecone(monkeypatch, captured)
    monkeypatch.setenv("VECTOR_BACKEND", "pinecone")
    idx = r.make_index()
    # avoid real embeddings — deterministic stub vector
    monkeypatch.setattr(type(idx), "_embed", lambda self, texts: [[0.1, 0.2, 0.3] for _ in texts])

    hits = idx.search("reset my password", tenant="meridian",
                      max_sensitivity="confidential", sources={"policies"}, k=3)

    # tenant -> namespace: structural isolation, a query hits exactly one namespace
    assert captured["query"]["namespace"] == "meridian"
    # sensitivity ceiling applied as a metadata filter BEFORE results (D-011): confidential == level 2
    assert captured["query"]["filter"]["sensitivity_level"] == {"$lte": 2}
    # source allow-list is a metadata filter, not a post-hoc pass
    assert captured["query"]["filter"]["source"] == {"$in": ["policies"]}
    # result shape is IDENTICAL to the in-memory backend's dicts (contract unchanged)
    assert hits and set(hits[0]) == {"id", "doc_id", "text", "source", "sensitivity", "score"}


def test_pinecone_add_upserts_per_tenant_namespace(monkeypatch):
    captured = {}
    _install_fake_pinecone(monkeypatch, captured)
    monkeypatch.setenv("VECTOR_BACKEND", "pinecone")
    idx = r.make_index()
    monkeypatch.setattr(type(idx), "_embed", lambda self, texts: [[0.0] * 3 for _ in texts])
    chunks = r.chunk_document("d1", "hello world.", source="policies", tenant="meridian", sensitivity="internal")
    idx.add(chunks)
    namespaces = [ns for ns, _ in captured["upserts"]]
    assert namespaces == ["meridian"]        # upserted into the tenant's namespace
    assert idx.chunks                          # local mirror updated (empty-check / seed_demo still work)

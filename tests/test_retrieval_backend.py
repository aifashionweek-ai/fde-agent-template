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


def _pinecone_filter_match(md: dict, flt: dict) -> bool:
    """Evaluate a Pinecone metadata filter the way the real store does (Mongo-style semantics):
    top-level keys AND together; $and/$or combine sub-filters; an ABSENT field matches nothing
    except `$exists: false`. Only the operators this repo uses are implemented — anything else raises."""
    for key, cond in flt.items():
        if key == "$and":
            if not all(_pinecone_filter_match(md, c) for c in cond): return False
        elif key == "$or":
            if not any(_pinecone_filter_match(md, c) for c in cond): return False
        else:
            present, val = key in md, md.get(key)
            for op, arg in cond.items():
                if op == "$exists":
                    if present != bool(arg): return False
                elif not present:
                    return False
                elif op == "$lte":
                    if not val <= arg: return False
                elif op == "$in":
                    vals = val if isinstance(val, list) else [val]
                    if not any(v in arg for v in vals): return False
                else:
                    raise ValueError(f"unsupported filter op {op}")
    return True


def _install_semantic_pinecone(monkeypatch):
    """A fake Pinecone that STORES upserts per namespace and EVALUATES query filters — so ACL tests
    exercise real filter behavior against real metadata, not just the filter's shape."""
    fake = types.ModuleType("pinecone")
    store: dict[str, list] = {}

    class FakeIndex:
        def upsert(self, vectors, namespace=None):
            store.setdefault(namespace, []).extend((v["id"], v["metadata"]) for v in vectors)

        def query(self, *, vector, top_k, namespace, filter, include_metadata):
            ms = [{"id": cid, "score": 0.5, "metadata": md}
                  for cid, md in store.get(namespace, []) if _pinecone_filter_match(md, filter or {})]
            return {"matches": ms[:top_k]}

    class Pinecone:
        def __init__(self, api_key=None): pass
        def Index(self, name): return FakeIndex()

    fake.Pinecone = Pinecone
    monkeypatch.setitem(sys.modules, "pinecone", fake)


def _semantic_pinecone_index(monkeypatch):
    _install_semantic_pinecone(monkeypatch)
    monkeypatch.setenv("VECTOR_BACKEND", "pinecone")
    idx = r.make_index()
    monkeypatch.setattr(type(idx), "_embed", lambda self, texts: [[0.0, 0.0, 0.0] for _ in texts])
    return idx


def _seed_acl_corpus(idx):
    """One open doc, one group-ACL'd doc, one cross-tenant doc — the D-036 access matrix."""
    idx.add(r.chunk_document("open-doc", "VPN reset steps, visible to any meridian employee.",
                             source="policies", tenant="meridian"))
    idx.add(r.chunk_document("legal-doc", "Legal hold procedure, legal team only.",
                             source="policies", tenant="meridian", meta={"allowed_groups": ["legal"]}))
    idx.add(r.chunk_document("acme-doc", "Acme internal runbook.", source="policies", tenant="acme"))


def _visible_docs(idx, *, tenant, groups):
    return {h["doc_id"] for h in idx.search("reset legal runbook", tenant=tenant,
                                            max_sensitivity="internal", groups=groups, k=10)}


def test_pinecone_open_doc_visible_under_group_filter(monkeypatch):
    """THE GAP (handoff item 1): an OPEN doc (no allowed_groups) must stay visible to a caller WITH
    groups — in-memory _group_ok returns True for it; a bare `allowed_groups: {$in: groups}` filter
    wrongly excludes it because the field doesn't exist on open docs."""
    idx = _semantic_pinecone_index(monkeypatch)
    _seed_acl_corpus(idx)
    seen = _visible_docs(idx, tenant="meridian", groups={"engineering"})
    assert "open-doc" in seen          # open doc must not vanish under a group filter
    assert "legal-doc" not in seen     # wrong group still never sees the ACL'd doc


def test_pinecone_acl_doc_hidden_from_caller_without_groups(monkeypatch):
    """The WORSE half of the gap: with groups=None the old code applied NO ACL filter at all, leaking
    ACL'd docs to a caller with no groups — in-memory _group_ok denies them (bool(None & acl) is False)."""
    idx = _semantic_pinecone_index(monkeypatch)
    _seed_acl_corpus(idx)
    seen = _visible_docs(idx, tenant="meridian", groups=None)
    assert "legal-doc" not in seen     # no groups -> only open docs
    assert "open-doc" in seen


def test_acl_decision_parity_with_in_memory(monkeypatch):
    """D-037 guard: BOTH backends make the SAME access decision across the whole matrix —
    open doc, right-group, wrong-group, no-groups caller, cross-tenant. One semantics, two stores."""
    mem = r.InMemoryIndex()
    _seed_acl_corpus(mem)
    pc = _semantic_pinecone_index(monkeypatch)
    _seed_acl_corpus(pc)
    matrix = [("right-group", {"legal"}), ("wrong-group", {"engineering"}),
              ("multi-group", {"legal", "sales"}), ("no-groups", None)]
    for name, groups in matrix:
        for tenant in ("meridian", "acme"):
            mem_seen = _visible_docs(mem, tenant=tenant, groups=groups)
            pc_seen = _visible_docs(pc, tenant=tenant, groups=groups)
            assert mem_seen == pc_seen, f"{name}/{tenant}: memory={mem_seen} pinecone={pc_seen}"


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

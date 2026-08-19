"""D-016/017/018: agentic memory. Scoping is structural, provenance + ttl enforced, forget works."""
import time, pathlib, tempfile, os
from agent.memory import MemoryStore, recall_context

def _store():
    f = tempfile.mktemp(suffix=".json"); return MemoryStore(path=f)

def test_tenant_user_isolation_is_structural():        # D-017
    s = _store()
    s.put("demo", "alice", "semantic", "unit_pref", "metric")
    s.put("acme", "bob", "semantic", "unit_pref", "imperial")
    hits = s.search("demo", "alice", "unit preference")
    assert hits and all(m.tenant == "demo" and m.user == "alice" for m in hits)
    assert not s.search("demo", "alice", "x", k=10) or all(m.user == "alice" for m in s.search("demo","alice","x",k=10))
    # alice cannot see bob/acme memory
    assert all(m.value != "imperial" for m in s.search("demo", "alice", "unit", k=10))

def test_upsert_by_scope_key():                        # D-016
    s = _store()
    a = s.put("demo", "alice", "semantic", "tier", "free")
    b = s.put("demo", "alice", "semantic", "tier", "enterprise")
    assert a.id == b.id                                # same scope+key -> upsert, not duplicate
    assert s.search("demo", "alice", "tier")[0].value == "enterprise"

def test_ttl_expiry():                                 # D-016
    s = _store()
    m = s.put("demo", "alice", "episodic", "old", "stale", ttl_days=1)
    m.created_at = time.time() - 2 * 86400
    s._items[m.id] = m
    assert m.expired()
    assert all(x.key != "old" for x in s.search("demo", "alice", "old", k=10))

def test_forget_right_to_be_forgotten():               # D-017
    s = _store()
    s.put("demo", "alice", "semantic", "a", "1"); s.put("demo", "alice", "semantic", "b", "2")
    assert s.forget("demo", "alice", key="a") == 1
    assert s.forget("demo", "alice") == 1              # remaining
    assert s.all_for("demo", "alice") == []

def test_recall_context_scoped():                      # D-016
    s = MemoryStore(path=tempfile.mktemp(suffix=".json"))
    import agent.memory as M; M.STORE = s
    s.put("demo", "alice", "semantic", "unit_pref", "prefers metric units")
    ctx = recall_context("demo", "alice", "what units should I use")
    assert "metric" in ctx
    assert recall_context("demo", "bob", "units") == ""   # different user sees nothing

def test_provenance_recorded():                        # D-017
    s = _store()
    m = s.put("demo", "alice", "semantic", "k", "v", source="human")
    assert m.source == "human" and m.created_at > 0

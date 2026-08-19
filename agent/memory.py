"""Agentic memory (D-016, D-017, D-018). Three kinds, because interviewers ask "how does it remember":

  1. SHORT-TERM / working  — the message list within one thread, checkpointed by thread_id.
                             Already handled by LangGraph's checkpointer in graph.py. Survives a turn,
                             an interrupt/resume, a crash — NOT other threads.
  2. LONG-TERM / semantic  — facts remembered ACROSS threads and sessions, scoped by (tenant, user).
                             "The customer prefers metric units", "account tier = enterprise".
                             Backed by a Store; retrieved by relevance and injected as context.
  3. EPISODIC              — past (task -> outcome) pairs, used as few-shot exemplars for similar tasks.
                             "Last time someone asked X, the good answer was Y."

This module is the LONG-TERM + EPISODIC layer. It's a thin, swappable interface over a store:
  - default: JSON file (zero infra, good for demo/tests)
  - prod:    LangGraph BaseStore (Postgres/Redis) or a vector store — same method surface

Memory is CUSTOMER DATA: every item is scoped by tenant, carries provenance + timestamp, and is
subject to the same residency/retention/right-to-be-forgotten rules as retrieval (docs/03).
Writes to long-term memory are gated: the agent proposes, a guard/human can dispose (D-004 pattern).
"""
from __future__ import annotations
import json, os, time, hashlib, pathlib, re
from dataclasses import dataclass, asdict, field
from typing import Optional, Literal

MemKind = Literal["semantic", "episodic"]

@dataclass
class Memory:
    id: str
    tenant: str
    user: str
    kind: MemKind
    key: str                      # short handle, e.g. "unit_preference" or a task fingerprint
    value: str                    # the remembered content
    created_at: float
    source: str = "agent"         # who wrote it: agent | human | ingestion
    ttl_days: Optional[int] = None
    meta: dict = field(default_factory=dict)

    def expired(self, now: float | None = None) -> bool:
        if self.ttl_days is None: return False
        return (now or time.time()) - self.created_at > self.ttl_days * 86400


class MemoryStore:
    """Swappable backend. Default = JSON file. Implement search/put/get/delete against any store."""
    def __init__(self, path: str | None = None):
        self.path = pathlib.Path(path or os.getenv("MEMORY_PATH", ".local/memory.json"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, Memory] = {}
        if self.path.exists():
            for d in json.loads(self.path.read_text() or "[]"):
                self._items[d["id"]] = Memory(**d)

    def _flush(self):
        self.path.write_text(json.dumps([asdict(m) for m in self._items.values()], indent=2))

    def put(self, tenant: str, user: str, kind: MemKind, key: str, value: str,
            source: str = "agent", ttl_days: int | None = None, meta: dict | None = None) -> Memory:
        mid = hashlib.sha1(f"{tenant}:{user}:{kind}:{key}".encode()).hexdigest()[:12]   # upsert by (scope,key)
        m = Memory(mid, tenant, user, kind, key, value, time.time(), source, ttl_days, meta or {})
        self._items[mid] = m; self._flush(); return m

    def search(self, tenant: str, user: str, query: str, kind: MemKind | None = None, k: int = 3) -> list[Memory]:
        """Scoped + relevance-ranked. Structural tenant+user isolation (never a soft boost), then lexical overlap.
        Swap the ranker for embeddings in prod; the SCOPING contract is what must not change."""
        now = time.time(); q = set(re.findall(r"[a-z0-9]+", query.lower()))
        cands = [m for m in self._items.values()
                 if m.tenant == tenant and m.user == user and (kind is None or m.kind == kind) and not m.expired(now)]
        def score(m: Memory) -> float:
            toks = set(re.findall(r"[a-z0-9]+", f"{m.key} {m.value}".lower()))
            overlap = len(q & toks) / (len(q) or 1)
            recency = 1.0 / (1.0 + (now - m.created_at) / 86400)     # newer ranks higher, gently
            return 0.8 * overlap + 0.2 * recency
        return sorted(cands, key=score, reverse=True)[:k]

    def all_for(self, tenant: str, user: str) -> list[Memory]:
        return [m for m in self._items.values() if m.tenant == tenant and m.user == user and not m.expired()]

    def forget(self, tenant: str, user: str, key: str | None = None) -> int:
        """Right-to-be-forgotten: delete one key or the whole user scope."""
        before = len(self._items)
        self._items = {i: m for i, m in self._items.items()
                       if not (m.tenant == tenant and m.user == user and (key is None or m.key == key))}
        self._flush(); return before - len(self._items)


STORE = MemoryStore()

def recall_context(tenant: str, user: str, task: str, k: int = 3) -> str:
    """Assemble a short memory block to inject into the agent's context before planning."""
    mems = STORE.search(tenant, user, task, k=k)
    if not mems: return ""
    lines = [f"- ({m.kind}) {m.key}: {m.value}" for m in mems]
    return "Relevant memory about this user:\n" + "\n".join(lines)

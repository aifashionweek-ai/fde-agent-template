"""Retrieval with document ROUTING (D-010, D-011). This is where customer data lands and how it's found.

Rules encoded here (each is a MASTERSCHEMA row + test):
  * Every chunk carries provenance: doc_id, source, tenant, sensitivity, ingested_at.  (D-010)
  * A query is scoped by tenant; cross-tenant retrieval is impossible, not just discouraged. (D-011)
  * Sensitivity is an allow-list: a request at level N never sees chunks > N.                 (D-011)
  * Hybrid scoring: BM25 (lexical) + optional embeddings (semantic); cheap first, semantic if available.
  * Returned ids are the ONLY valid citations; output_guard enforces grounding.              (D-012)

Swap the in-memory store for OpenSearch / Pinecone / pgvector by implementing VectorIndex.search();
the routing contract above does not change — that's the point.
"""
from __future__ import annotations
import json, math, os, re, time, hashlib
from dataclasses import dataclass, asdict
from typing import Iterable, Optional

SENSITIVITY = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}

@dataclass
class Chunk:
    doc_id: str; chunk_id: str; text: str; source: str; tenant: str
    sensitivity: str = "internal"; ingested_at: float = 0.0; meta: dict | None = None

def chunk_document(doc_id: str, text: str, *, source: str, tenant: str, sensitivity: str = "internal",
                   size: int = 700, overlap: int = 100, meta: dict | None = None) -> list[Chunk]:
    """Sentence-aware fixed-size chunking with overlap. Provenance is attached at ingestion, never inferred later."""
    assert sensitivity in SENSITIVITY, f"unknown sensitivity {sensitivity}"
    sents = re.split(r"(?<=[.!?])\s+", text.strip()); out, buf = [], ""
    for s in sents:
        if len(buf) + len(s) > size and buf:
            out.append(buf); buf = buf[-overlap:] + " " + s
        else: buf = (buf + " " + s).strip()
    if buf: out.append(buf)
    now = time.time()
    return [Chunk(doc_id, f"{doc_id}#{i}", c, source, tenant, sensitivity, now, meta or {}) for i, c in enumerate(out)]

class _BM25:
    def __init__(self, docs: list[list[str]], k1=1.5, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.N = len(docs); self.avgdl = sum(map(len, docs)) / max(self.N, 1)
        self.df: dict[str, int] = {}
        for d in docs:
            for t in set(d): self.df[t] = self.df.get(t, 0) + 1
    def score(self, q: list[str], i: int) -> float:
        d = self.docs[i]; dl = len(d); tf: dict[str, int] = {}
        for t in d: tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in q:
            if t not in tf: continue
            idf = math.log(1 + (self.N - self.df[t] + 0.5) / (self.df[t] + 0.5))
            s += idf * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

def _tok(s: str) -> list[str]: return re.findall(r"[a-z0-9]+", s.lower())

class InMemoryIndex:
    """Hybrid index. Embeddings are optional (EMBED_PROVIDER=openai|none); BM25 always on."""
    def __init__(self): self.chunks: list[Chunk] = []; self._bm25 = None; self._emb: list[list[float]] | None = None
    def add(self, chunks: Iterable[Chunk]):
        self.chunks.extend(chunks); self._bm25 = _BM25([_tok(c.text) for c in self.chunks]); self._emb = None
    def _embed(self, texts: list[str]) -> list[list[float]] | None:
        if os.getenv("EMBED_PROVIDER", "none") != "openai": return None
        from openai import OpenAI
        r = OpenAI().embeddings.create(model=os.getenv("EMBED_MODEL", "text-embedding-3-small"), input=texts)
        return [d.embedding for d in r.data]
    def search(self, query: str, *, tenant: str, max_sensitivity: str = "internal",
               sources: Optional[set[str]] = None, k: int = 5) -> list[dict]:
        lvl = SENSITIVITY[max_sensitivity]
        # ROUTING: tenant + sensitivity + source allow-list applied BEFORE scoring (D-011).
        idx = [i for i, c in enumerate(self.chunks)
               if c.tenant == tenant and SENSITIVITY[c.sensitivity] <= lvl and (sources is None or c.source in sources)]
        if not idx: return []
        q = _tok(query); lex = {i: self._bm25.score(q, i) for i in idx}
        mx = max(lex.values()) or 1.0; scores = {i: lex[i] / mx for i in idx}
        if self._emb is None and os.getenv("EMBED_PROVIDER", "none") != "none":
            self._emb = self._embed([c.text for c in self.chunks])
        if self._emb:
            qv = self._embed([query])[0]
            def cos(a, b): return sum(x*y for x, y in zip(a, b)) / (math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(y*y for y in b)) + 1e-9)
            for i in idx: scores[i] = 0.5 * scores[i] + 0.5 * cos(qv, self._emb[i])
        top = sorted(idx, key=lambda i: -scores[i])[:k]
        return [{"id": self.chunks[i].chunk_id, "doc_id": self.chunks[i].doc_id, "text": self.chunks[i].text,
                 "source": self.chunks[i].source, "sensitivity": self.chunks[i].sensitivity,
                 "score": round(scores[i], 4)} for i in top]

INDEX = InMemoryIndex()

def load_dir(path: str, *, tenant: str, source: str, sensitivity: str = "internal") -> int:
    """Ingest a folder of .txt/.md as one tenant+source. Provenance decided by the caller at landing time."""
    import pathlib
    n = 0
    for p in sorted(pathlib.Path(path).glob("**/*")):
        if p.suffix.lower() in {".txt", ".md"}:
            doc_id = hashlib.sha1(str(p).encode()).hexdigest()[:10]
            INDEX.add(chunk_document(doc_id, p.read_text(errors="ignore"), source=source, tenant=tenant,
                                     sensitivity=sensitivity, meta={"path": str(p)})); n += 1
    return n

def seed_demo():
    """Tiny built-in corpus so search_kb returns real citations out of the box."""
    if INDEX.chunks: return
    INDEX.add(chunk_document("refund-policy", "Refunds are issued within 14 days of purchase for unused items. "
        "Digital goods are non-refundable. Contact support with the order id to start a refund.",
        source="policies", tenant="demo", sensitivity="public"))
    INDEX.add(chunk_document("sla", "Enterprise SLA: 99.9% monthly uptime. Credits of 10% per 0.1% below target. "
        "Support response within 1 business hour for P1.", source="contracts", tenant="demo", sensitivity="internal"))
    INDEX.add(chunk_document("secret-pricing", "Confidential: Q4 enterprise discount floor is 35%.",
        source="sales", tenant="demo", sensitivity="confidential"))
    INDEX.add(chunk_document("other-tenant", "Acme Corp internal runbook: rotate keys every 30 days.",
        source="runbooks", tenant="acme", sensitivity="internal"))

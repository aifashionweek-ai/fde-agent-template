"""Document ingestion (D-032) — the stage BEFORE retrieval. Parses real enterprise documents with
Unstructured.io (Apache-2.0, the library production RAG teams use), strips header/footer boilerplate,
fixes encoding, and emits tenant/sensitivity-tagged chunks via the SAME chunk_document() the rest of the
pipeline uses — so provenance tagging is identical whether a doc arrives by seed, load_dir, or ingestion.

`unstructured` and `ftfy` are OPTIONAL (requirements-ingest.txt) — importing this module never requires
them, so `python update.py --check` and the core install work without them. When installed, `partition()`
runs the REAL parser (auto-detects PDF/DOCX/HTML/PPTX/scanned images). This is not a passthrough: the
default `fast` strategy uses pdfminer to extract real text elements; `hi_res` (env INGEST_STRATEGY=hi_res)
adds layout detection and needs the poppler system dep (`brew install poppler` / `apt-get install
poppler-utils`).

    from agent.ingest import ingest_directory
    stats = ingest_directory("data/sample_corpus", tenant="meridian", sensitivity="internal")
    print(stats.as_dict())   # {files_processed, chunks_produced, bytes_in, files_skipped, ...}

Same interface at any scale: point it at a local folder for the demo, or an object-storage mount (S3) in
production — the caller and the downstream contract don't change.
"""
from __future__ import annotations
import os, pathlib, hashlib
from dataclasses import dataclass, field

from .retrieval import chunk_document, INDEX
from .logging_setup import log

# Extensions unstructured's auto partitioner handles; anything else is skipped (counted, logged).
SUPPORTED = {".pdf", ".docx", ".doc", ".html", ".htm", ".pptx", ".ppt", ".txt", ".md", ".eml", ".rtf", ".odt", ".epub"}
# Element categories unstructured tags as non-content boilerplate — dropped for cleaner chunks.
BOILERPLATE = {"Header", "Footer", "PageBreak", "PageNumber"}


def _require_partition():
    try:
        from unstructured.partition.auto import partition
        return partition
    except ImportError as e:  # optional dep — actionable message, never a silent stub
        raise ImportError(
            "document ingestion needs Unstructured: `pip install -r requirements-ingest.txt` "
            "(+ the poppler system dep for hi_res/image PDFs). Core + update.py --check run without it."
        ) from e


def _clean(text: str) -> str:
    """Real cleaning: ftfy fixes mojibake/encoding if installed; drop blank + bare page-number lines."""
    try:
        import ftfy
        text = ftfy.fix_text(text)
    except ImportError:
        pass
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln and not ln.isdigit())


@dataclass
class IngestStats:
    files_processed: int = 0
    files_skipped: int = 0
    chunks_produced: int = 0
    bytes_in: int = 0
    skipped: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"files_processed": self.files_processed, "files_skipped": self.files_skipped,
                "chunks_produced": self.chunks_produced, "bytes_in": self.bytes_in,
                "skipped": self.skipped}


def _document_id(source_uri) -> str:
    """Stable id keyed by the document's location (URI/path) — survives content changes so a modified
    document REPLACES its old chunks rather than duplicating them (D-036)."""
    return hashlib.sha1(str(source_uri).encode()).hexdigest()[:10]


def _parse(path, strategy):
    """Run the REAL parser + clean. Returns (text, n_elements, strategy) or None on unparseable/empty."""
    partition = _require_partition()
    p = pathlib.Path(path)
    strategy = strategy or os.getenv("INGEST_STRATEGY", "fast")
    try:
        els = partition(filename=str(p), strategy=strategy)
    except Exception as e:
        log.warning("ingest_parse_failed", path=str(p), error=f"{type(e).__name__}: {e}")
        return None
    texts = [getattr(el, "text", "") or "" for el in els if getattr(el, "category", "") not in BOILERPLATE]
    text = _clean("\n".join(texts))
    if not text.strip():
        log.warning("ingest_empty", path=str(p), elements=len(els))
        return None
    return text, len(els), strategy


def _chunks_from_text(p, text, n_els, strategy, *, tenant, sensitivity, allowed_groups, version):
    """Build tagged chunks with FULL lifecycle + ACL provenance. Retrieved content is treated as UNTRUSTED
    (an indirect-injection surface) — never as instructions; only tools + authz can act."""
    source_uri = str(p.resolve()) if p.exists() else str(p)
    document_id = _document_id(source_uri)
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    meta = {"source_id": p.stem, "document_id": document_id, "document_version": version,
            "content_hash": content_hash[:16], "content_hash_full": content_hash,
            "source_uri": source_uri, "parser": f"unstructured:{strategy}", "elements": n_els,
            "allowed_groups": list(allowed_groups) if allowed_groups else None,
            "UNTRUSTED": True}                              # indirect-injection surface — content is data, not orders
    chunks = chunk_document(document_id, text, source=p.stem, tenant=tenant, sensitivity=sensitivity, meta=meta)
    return chunks, content_hash, document_id


def ingest_document(path, *, tenant: str, sensitivity: str = "internal", allowed_groups=None,
                    strategy: str | None = None):
    """Parse ONE document into cleaned, tenant/sensitivity/ACL-tagged chunks (list[Chunk]).
    A corrupt/empty/unparseable file is logged and returns [] — it never raises (J-05 honest skip)."""
    p = pathlib.Path(path)
    r = _parse(p, strategy)
    if r is None:
        return []
    text, n_els, strat = r
    chunks, _, _ = _chunks_from_text(p, text, n_els, strat, tenant=tenant, sensitivity=sensitivity,
                                     allowed_groups=allowed_groups, version=1)
    log.info("ingest_document", path=str(p), elements=n_els, chunks=len(chunks))
    return chunks


class IngestLedger:
    """Tracks ingested documents by content hash so re-ingestion is a content-hash LIFECYCLE, not a
    blind re-add: unchanged→skip, new→add, modified→replace, identical-content-elsewhere→dedup (D-036)."""
    def __init__(self):
        self.by_doc: dict[str, str] = {}       # document_id -> content_hash
        self.versions: dict[str, int] = {}     # document_id -> version


def sync_document(index, path, *, tenant: str, sensitivity: str = "internal", allowed_groups=None,
                  ledger: IngestLedger, strategy: str | None = None) -> str:
    """Content-hash lifecycle for ONE document. Returns: 'added' | 'skipped' (unchanged) | 'replaced'
    (modified — old chunks deleted, re-chunked) | 'deduped' (identical content under a different uri) |
    'empty' (unparseable)."""
    p = pathlib.Path(path)
    r = _parse(p, strategy)
    if r is None:
        return "empty"
    text, n_els, strat = r
    source_uri = str(p.resolve()) if p.exists() else str(p)
    document_id = _document_id(source_uri)
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    owner = next((d for d, h in ledger.by_doc.items() if h == content_hash), None)
    if owner == document_id:
        return "skipped"                                   # identical content, same document → nothing to do
    if owner is not None:
        return "deduped"                                   # identical content under a different uri → skip
    version = ledger.versions.get(document_id, 0) + 1
    chunks, _, _ = _chunks_from_text(p, text, n_els, strat, tenant=tenant, sensitivity=sensitivity,
                                     allowed_groups=allowed_groups, version=version)
    action = "added"
    if document_id in ledger.by_doc:
        index.remove_document(document_id)                 # modified → replace old vectors
        action = "replaced"
    index.add(chunks)
    ledger.by_doc[document_id] = content_hash
    ledger.versions[document_id] = version
    log.info("sync_document", path=str(p), action=action, version=version, chunks=len(chunks))
    return action


def delete_document(index, path, ledger: IngestLedger) -> int:
    """Remove a deleted source document's vectors + ledger entry. Returns chunks removed (D-036)."""
    p = pathlib.Path(path)
    document_id = _document_id(str(p.resolve()) if p.exists() else str(p))
    removed = index.remove_document(document_id)
    ledger.by_doc.pop(document_id, None)
    ledger.versions.pop(document_id, None)
    log.info("delete_document", path=str(p), removed=removed)
    return removed


def ingest_directory(path, *, tenant: str, sensitivity: str = "internal", index=None,
                     strategy: str | None = None) -> IngestStats:
    """Walk a folder, ingest every SUPPORTED file, index the chunks, return REAL counts. Unsupported
    extensions and unparseable files are skipped (counted), never fatal. Same interface for a 5-file
    demo folder or a 10GB object-storage mount — production just changes `path`."""
    index = INDEX if index is None else index
    stats = IngestStats()
    for f in sorted(pathlib.Path(path).rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in SUPPORTED:
            stats.files_skipped += 1
            stats.skipped.append(f"{f.name} (unsupported)")
            continue
        stats.bytes_in += f.stat().st_size
        chunks = ingest_document(f, tenant=tenant, sensitivity=sensitivity, strategy=strategy)
        if not chunks:
            stats.files_skipped += 1
            stats.skipped.append(f"{f.name} (empty/unparseable)")
            continue
        index.add(chunks)
        stats.files_processed += 1
        stats.chunks_produced += len(chunks)
    log.info("ingest_directory", path=str(path), **stats.as_dict())
    return stats


if __name__ == "__main__":
    import sys, json
    d = sys.argv[1] if len(sys.argv) > 1 else "data/sample_corpus"
    st = ingest_directory(d, tenant=os.getenv("TENANT", "meridian"),
                          sensitivity=os.getenv("MAX_SENSITIVITY", "internal"))
    print(json.dumps(st.as_dict(), indent=2))

"""D-032 guard: real document ingestion via Unstructured.io. Parses a real PDF into tenant/sensitivity-
tagged chunks that retrieve, and skips corrupt/empty/unsupported files without crashing.

`unstructured` is an OPTIONAL extra (requirements-ingest.txt); if it isn't installed this module skips
cleanly so `update.py --check` stays green on the core install. Where it IS installed (as in this repo's
env), these run the REAL parser — no passthrough."""
import pathlib
import pytest

pytest.importorskip("unstructured")  # ingestion extra optional — skip whole module if absent

from agent.ingest import ingest_document, ingest_directory, _clean, SUPPORTED
from agent.retrieval import InMemoryIndex

CORPUS = pathlib.Path(__file__).parent.parent / "data" / "sample_corpus"
REAL_PDF = CORPUS / "nist-ir-7621r1-smallbiz-infosec.pdf"


def test_real_pdf_ingests_tags_and_retrieves():
    assert REAL_PDF.exists(), "sample corpus PDF missing"
    chunks = ingest_document(REAL_PDF, tenant="meridian", sensitivity="internal")
    assert chunks, "real PDF parsed to zero chunks — parser not actually running"
    c0 = chunks[0]
    assert c0.tenant == "meridian" and c0.sensitivity == "internal"      # identical tagging as the rest
    assert c0.text.strip()
    assert c0.meta.get("parser", "").startswith("unstructured")          # real parser recorded, not a stub
    assert len(c0.meta.get("content_hash", "")) == 16
    idx = InMemoryIndex(); idx.add(chunks)
    hits = idx.search("information security", tenant="meridian", max_sensitivity="internal", k=3)
    assert hits, "ingested NIST content is not retrievable"
    assert all(h["id"].count("#") == 1 for h in hits)                    # provenance chunk ids intact


def test_corrupt_empty_and_unsupported_are_skipped_not_crash(tmp_path):
    (tmp_path / "broken.pdf").write_bytes(b"%PDF-1.4 not really a pdf \x00\x01\x02\x03")
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / "notes.xyz").write_text("unsupported extension")
    idx = InMemoryIndex()
    stats = ingest_directory(tmp_path, tenant="meridian", index=idx)     # must NOT raise
    assert stats.files_processed == 0
    assert stats.files_skipped >= 3
    assert idx.chunks == []                                              # nothing bad got indexed


def test_clean_fixes_encoding_and_strips_boilerplate():
    assert _clean("line1\n\n42\n  line2  ") == "line1\nline2"            # blank + bare page-number dropped


def test_supported_covers_common_enterprise_types():
    assert {".pdf", ".docx", ".html", ".pptx"} <= SUPPORTED

"""D-036 guard: ingestion lifecycle + document ACLs. Content-hash drives skip/upsert/replace/dedup/delete;
retrieval enforces tenant AND sensitivity≤clearance AND allowed_groups∩principal.groups. Catch-proof: a
doc ACL'd to 'legal' is invisible to 'engineering'; a deleted doc's vectors are gone; a modified doc
re-indexes; identical content is deduped."""
import pathlib
import pytest

pytest.importorskip("unstructured")

from agent.ingest import sync_document, delete_document, ingest_document, IngestLedger
from agent.retrieval import InMemoryIndex


def _write(p, text):
    p.write_text(text); return p


def test_new_then_unchanged_skips(tmp_path):
    f = _write(tmp_path / "policy.txt", "VPN access requires MFA. Rotate keys every 90 days.")
    idx, led = InMemoryIndex(), IngestLedger()
    assert sync_document(idx, f, tenant="meridian", ledger=led) == "added"
    n = len(idx.chunks)
    assert sync_document(idx, f, tenant="meridian", ledger=led) == "skipped"      # unchanged content
    assert len(idx.chunks) == n                                                    # no duplicate chunks


def test_modified_replaces_and_reindexes(tmp_path):
    f = _write(tmp_path / "policy.txt", "Rotate keys every 90 days.")
    idx, led = InMemoryIndex(), IngestLedger()
    sync_document(idx, f, tenant="meridian", ledger=led)
    _write(f, "Rotate keys every 30 days now, per updated security policy.")
    assert sync_document(idx, f, tenant="meridian", ledger=led) == "replaced"
    texts = " ".join(c.text for c in idx.chunks)
    assert "30 days" in texts and "90 days" not in texts                           # old chunks gone
    assert idx.chunks[0].meta["document_version"] == 2                             # version bumped


def test_deleted_removes_vectors(tmp_path):
    f = _write(tmp_path / "policy.txt", "Some deletable policy content about access.")
    idx, led = InMemoryIndex(), IngestLedger()
    sync_document(idx, f, tenant="meridian", ledger=led)
    assert idx.chunks
    removed = delete_document(idx, f, led)
    assert removed > 0 and idx.chunks == [] and not led.by_doc                     # vectors + ledger cleared


def test_dedup_identical_content_under_new_path(tmp_path):
    body = "Identical handbook text about acceptable use and access control."
    a = _write(tmp_path / "a.txt", body)
    b = _write(tmp_path / "b.txt", body)
    idx, led = InMemoryIndex(), IngestLedger()
    assert sync_document(idx, a, tenant="meridian", ledger=led) == "added"
    n = len(idx.chunks)
    assert sync_document(idx, b, tenant="meridian", ledger=led) == "deduped"       # same content, new uri
    assert len(idx.chunks) == n


def test_doc_acl_invisible_to_wrong_group(tmp_path):
    f = _write(tmp_path / "legal.txt", "Confidential legal memo regarding vendor access controls.")
    idx = InMemoryIndex()
    idx.add(ingest_document(f, tenant="meridian", sensitivity="internal", allowed_groups=["legal"]))
    assert idx.search("access controls", tenant="meridian", groups={"engineering"}, k=5) == []   # ACL blocks
    assert idx.search("access controls", tenant="meridian", groups={"legal"}, k=5)                # legal sees it


def test_lifecycle_metadata_is_complete(tmp_path):
    f = _write(tmp_path / "doc.txt", "Access policy content for provenance metadata test.")
    chunks = ingest_document(f, tenant="meridian", sensitivity="internal", allowed_groups=["legal"])
    m = chunks[0].meta
    for k in ("source_id", "document_id", "document_version", "content_hash", "source_uri", "allowed_groups"):
        assert k in m, f"missing metadata field {k}"
    assert m["UNTRUSTED"] is True                                                  # indirect-injection surface flagged
    assert m["allowed_groups"] == ["legal"]

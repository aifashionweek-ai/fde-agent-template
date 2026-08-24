# SLOT 2: CORPUS

Drop the domain's documents here (or point `agent/retrieval.load_dir()` / `agent/ingest.py` at them).

How-to:
- `load_dir("corpus", tenant="<t>", source="<s>", sensitivity="internal")` ingests .txt/.md with provenance.
- For PDFs/DOCX/etc use `agent/ingest.py` (Unstructured.io, optional dep).
- Tag tenant / source / sensitivity at landing time — retrieval routing filters on those BEFORE scoring.

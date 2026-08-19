# 03 · Retrieval and customer data — where documents land, how they're found, what never leaks

This is the FDE's actual job: getting a customer's data in front of a model safely and usefully. `agent/retrieval.py` is small on purpose — the *contract* is what matters, and the store behind it is swappable.

## 1. Where a document lands (the provenance rule, D-010)
Every chunk carries `{doc_id, chunk_id, source, tenant, sensitivity, ingested_at, meta}` **decided at ingestion by the caller**, never inferred later by the model. If you can't say who owns a document and how sensitive it is at the moment it lands, it doesn't land.

```
load_dir("s3://…/acme/contracts", tenant="acme", source="contracts", sensitivity="confidential")
```

## 2. How a query is routed (D-011) — filters happen *before* scoring
1. **tenant** — hard filter. Cross-tenant retrieval is structurally impossible (tested: `test_tenant_isolation_is_structural`).
2. **sensitivity ceiling** — `public < internal < confidential < restricted`; the request carries its ceiling (from the caller's role), chunks above it are invisible.
3. **source allow-list** — optional; "answer only from contracts + policies."
4. *Then* hybrid scoring: BM25 always (free, exact terms, great for ids/SKUs/error codes) + cosine on embeddings when `EMBED_PROVIDER` is set (semantics, paraphrase). 50/50 fusion; tune per corpus.
5. Top-k ids are returned **and become the only legal citations** (D-012).

Why filter-then-score instead of score-then-filter: a soft "boost" can be out-ranked; a filter can't. Security properties must be *structural*.

## 3. Choosing the store (the contract doesn't change)
| Need | Use | Notes |
|---|---|---|
| demo / <50k chunks / 3-hour build | `InMemoryIndex` (this repo) | zero infra, BM25 + optional embeddings |
| customer already on AWS, wants one bill | **OpenSearch Serverless** (k-NN + BM25 native) | metadata filters map 1:1 to tenant/sensitivity |
| already on Postgres | **pgvector** | filters are `WHERE` clauses; row-level security = tenant isolation for free |
| managed, fast, multi-tenant namespaces | **Pinecone** (namespaces = tenants) | you reuse it at AIFW today |
| large doc sets + permissions sync from SharePoint/Drive | **Bedrock Knowledge Bases** | handles chunking + metadata filters; less control over chunker |

Implement `search(query, tenant, max_sensitivity, sources, k)` against any of them; keep the routing rules in one place.

## 4. Chunking and document types (what actually moves the needle)
- **Sentence-aware fixed windows with overlap** (default 700/100 chars) beat naive splits; tables/PDFs need a layout-aware parser (Unstructured, Docling, Textract) — keep table rows together.
- Store a **parent pointer**: retrieve small chunks for precision, hand the model the parent section for context.
- Put **titles/headers into the chunk text** — BM25 and embeddings both benefit.
- Freshness: `ingested_at` lets you prefer newer versions and expire stale ones; versioned docs keep the same `doc_id`, new `ingested_at`.

## 5. Customer data handling — the non-negotiables
- **Data minimization:** ingest what the use case needs; `sensitivity` defaults to `internal`, never `public`.
- **PII:** redact *before* the model (D-005, Presidio for real corpora), redact again on egress; keep a hash-map only if re-identification is a requirement and is contractually allowed.
- **Residency:** if data can't leave the account, `DATA_RESIDENCY=customer_vpc` (Bedrock) or `self_hosted` — and embeddings must follow the same rule (Bedrock Titan/Cohere embeddings, or an open embedder on their GPU), not OpenAI.
- **Retention:** traces contain prompts → LangSmith/Braintrust retention must match the customer's DPA; self-host Langfuse if it can't.
- **Right to be forgotten:** delete by `doc_id` everywhere (index, traces, eval datasets). Design for it day one.
- **Evaluation data is customer data:** golden sets derived from prod live under the same controls.

## 6. The tuning ladder (cheapest first — docs/08)
zero-shot → few-shot from golden set → better retrieval (chunking, hybrid, reranker) → tool/contract changes → fine-tune an open model on *their* labeled slice. Most "we need to fine-tune" requests are retrieval problems.

## 7. Interview line
"Provenance at ingestion, routing before ranking, citations only from what was retrieved. That's three lines of policy and it's what makes multi-tenant RAG safe. The store is a detail; the contract isn't."

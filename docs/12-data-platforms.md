# 12 · Where the customer's data lives — data platforms

The agent never hardcodes a database. It touches customer data in four places, each behind a contract,
so the customer's existing platform plugs in without changing the agent.

## The four data surfaces
| Surface | What it holds | Demo backend | Real enterprise backends |
|---|---|---|---|
| Retrieval (`agent/retrieval.py`) | documents + embeddings | in-memory BM25 | **Pinecone** (default), pgvector, OpenSearch, Databricks Vector Search, Snowflake Cortex Search |
| SQL / structured (`sql_query` tool) | business records | in-memory | Snowflake, Databricks, BigQuery, Redshift, Oracle |
| Memory (`agent/memory.py`) | durable user facts | JSON file | Postgres, DynamoDB, Redis |
| Traces / evals | prompts, scores | local JSON | LangSmith, Braintrust (self-hosted for residency) |

## The vector store decision (Databricks vs Snowflake vs Pinecone vs Oracle)
The retrieval contract is `search(query, tenant, sensitivity, k)`. Any store that supports metadata
filtering + vector search implements it. The choice is about where the customer's data already lives:
- **Pinecone** — managed, fast, namespaces map cleanly to tenants (isolation for free). Default here; matches the AIFW production stack.
- **Databricks Vector Search** — when the customer's data + governance already live in the Databricks lakehouse (Unity Catalog).
- **Snowflake Cortex Search** — when the warehouse is Snowflake and they want retrieval next to the data.
- **pgvector / OpenSearch** — when they want it in infra they already run.
- **Oracle 23ai vector** — when it's an Oracle shop.

The point an FDE makes: *"I don't move the customer's data to my vector store — I put the retrieval
contract in front of theirs. Tenant = namespace, sensitivity = metadata filter, applied before ranking."*

## Pinecone as the demo default (D-024)
`VECTOR_BACKEND=pinecone` swaps the in-memory index for Pinecone behind the same contract: one namespace
per tenant, a `sensitivity` metadata field filtered at query time. The in-memory backend stays the
zero-setup default so `make run` works with no accounts. Same pattern as AIFW production.

## Residency note
For regulated customers (healthcare/energy — Hang Ten's customers), the vector store, warehouse, and
memory all live in the customer's cloud/VPC, and inference runs via Bedrock in-account. No customer data
leaves their boundary — which is why the open-weights-on-Bedrock path (docs/02, docs/11) matters.

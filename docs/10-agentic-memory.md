# 10 · Agentic memory — the three kinds, and how this template implements each

Interviewers probe memory because it's where most "agents" are actually just stateless prompt calls. Be precise: there are **three** kinds, they have different scopes and backends, and conflating them is the tell.

## The three kinds
| Kind | Question it answers | Scope | Lifetime | Backend here | Prod backend |
|---|---|---|---|---|---|
| **Short-term / working** | "what did we say *this* conversation?" | one `thread_id` | one thread (survives interrupt/resume/crash via checkpoint) | LangGraph `MemorySaver` | Postgres/Redis checkpointer |
| **Long-term / semantic** | "what do I know about *this user*, ever?" | `(tenant, user)` | across all sessions | `agent/memory.py` Store (JSON) | LangGraph `BaseStore` on Postgres, or a vector store |
| **Episodic** | "how did a *similar task* go last time?" | `(tenant, user)` | across sessions | same Store, `kind=episodic` | vector store of (task→outcome) |

## How it works in this template (`agent/memory.py`)
- **Short-term** is already handled: the checkpointer keys the message list by `thread_id` (graph.py). Resume a thread, the messages are there.
- **Long-term/episodic** is the `MemoryStore`: `put(tenant, user, kind, key, value)`, `search(...)` (scoped + ranked), `forget(...)`. At the start of every run, `guard_input` calls `recall_context()` and injects a memory block into the system context *before* planning — so memory actually changes behaviour, not just sits in a table.
- The agent can **write** memory with the `remember` tool and **read** it with `recall_memory`. `remember` is a side effect → approval-gated (D-018): the agent proposes a durable fact, a human/guard disposes.

## Memory is customer data (the part that matters to an FDE)
Every item carries `tenant`, `user`, `source` (agent/human/ingestion), `created_at`, optional `ttl_days`. Therefore:
- **Isolation is structural** — `search` filters by `(tenant, user)` *before* ranking; cross-user recall is impossible, not discouraged (tested: `test_tenant_user_isolation_is_structural`).
- **Right to be forgotten** — `forget(tenant, user, key=None)` deletes one fact or the whole user scope (tested).
- **Retention** — `ttl_days` expires episodic memory; semantic facts persist until forgotten.
- **Residency** — the Store lives wherever the customer's data must live; swap JSON → their Postgres/vector DB, the scoping contract doesn't change.

## What NOT to remember (a guardrail, not a feature)
Don't persist transient chatter, PII beyond what's necessary, or anything you can't justify to the customer's DPA. `remember` being approval-gated is the enforcement point: durable memory is a decision, not a reflex.

## Scaling
- Demo: JSON file, exact-match + lexical ranking — fine to ~thousands of items.
- Real: LangGraph `BaseStore` (Postgres) for durability + transactions, or a vector store (pgvector/Pinecone) when you want *semantic* recall ("this is like that other thing") rather than key lookup. Same `search()` surface.
- Consolidation: periodically summarize many episodic items into fewer semantic facts (a background job), so context stays small.

## Interview line
"Three memories: working memory is the checkpointed thread; long-term semantic memory is facts about the user, scoped by tenant and injected before planning; episodic memory is past task outcomes for few-shot. All three are customer data — structurally isolated, provenance-stamped, forgettable — and writing to long-term memory is an approval-gated side effect, because durable memory is a decision."

"""Quality scorers — graded 0..1 with EXPLICIT thresholds (D-046). Deterministic where possible so they
run in CI; judge-based scorers (answer relevance, plan efficiency) are Braintrust/nightly (see README).

Each scorer(row) -> {"score": float, "detail": str}. THRESHOLDS[layer] is the mean-score floor the gate
enforces. Reuses the same retrieval + grounding code the graph uses."""
from __future__ import annotations

from agent.retrieval import InMemoryIndex, chunk_document
from agent.guards import output_guard, GuardError

THRESHOLDS = {
    "retrieval_quality": 0.70,     # mean recall@k — did routing surface the relevant docs in the top-k
    "groundedness": 1.00,          # citation-faithfulness on labeled traps is an invariant-grade check
}


def score_retrieval_quality(row: dict) -> dict:
    """recall@k = (relevant ∩ top-k) / relevant — did routing surface the relevant docs (the property that
    matters for RAG faithfulness). precision@k is reported alongside for context. Gate is on recall@k."""
    idx = InMemoryIndex()
    for c in row["corpus"]:
        idx.add(chunk_document(c["doc_id"], c["text"], source=c.get("source", "s"),
                               tenant=c["tenant"], sensitivity=c.get("sensitivity", "internal")))
    k = row.get("k", 3)
    hits = idx.search(row["query"], tenant=row["tenant"], k=k)
    got = [h["doc_id"] for h in hits]
    relevant = set(row["relevant_doc_ids"])
    found = sum(1 for d in relevant if d in got)
    recall = found / len(relevant) if relevant else 0.0
    precision = (sum(1 for d in got if d in relevant) / len(got)) if got else 0.0
    return {"score": round(recall, 3), "detail": f"recall@{k}={recall:.2f} precision@{k}={precision:.2f} got={got}"}


def score_groundedness(row: dict) -> dict:
    """Citation faithfulness: run the real grounding guard and compare its verdict to the label.
    score 1.0 iff the guard's grounded-ness matches expected_grounded (catches fabricated-citation and
    confident-no-evidence traps)."""
    raw = {"answer": row["answer"], "confidence": row.get("confidence", 0.9),
           "citations": row.get("citations", []), "actions": []}
    retrieved = set(row.get("retrieved_ids", []))
    predicted = True
    detail = ""
    try:
        out = output_guard(raw, retrieved_ids=retrieved)
        # grounded == every claimed citation resolved AND not a confident claim with no evidence
        cites = row.get("citations", [])
        all_resolve = all(c in retrieved for c in cites)
        confident_no_ev = (not cites) and row.get("confidence", 0.9) > 0.7
        predicted = all_resolve and not confident_no_ev
        detail = f"conf_after={out.confidence} cites_after={out.citations}"
    except GuardError as e:                               # strict grounding rejects -> not grounded
        predicted = False
        detail = str(e)
    match = predicted == row["expected_grounded"]
    return {"score": 1.0 if match else 0.0, "detail": f"predicted={predicted} expected={row['expected_grounded']} {detail}"}


SCORERS = {
    "retrieval_quality": score_retrieval_quality,
    "groundedness": score_groundedness,
}

# SNIPPET · per-layer telemetry span (D-044). The graph already wraps every node in one; this is how.
# ADAPT: decorate a graph node with @node_span("your_layer_name"). The name becomes part of state["path"]
#        AND opens a telemetry span — real token usage lands in it live (via RecordingLLM), and tool/hash/
#        status detail is read from state+output after the node. Telemetry only OBSERVES; a telemetry error
#        is swallowed so instrumentation can never change control flow or break a run.
# SEE IT: after a /run, GET /trace/<thread_id> returns the spans; the /dashboard renders them.

from agent.state import AgentState
from agent.tracing import node_span


@node_span("my_layer")                 # <- this string is the span/layer name and the path entry
def my_node(s: AgentState) -> dict:
    # ... do the node's work; call llm().invoke(...) here and tokens are captured automatically ...
    result = {"answer": "…", "confidence": 0.5, "citations": [], "actions": []}
    return {"result": result, "path": s.get("path", []) + ["my_layer"]}


# Reading the last run's spans programmatically (what /trace and the dashboard use):
#     from agent import telemetry
#     rec = telemetry.last_run(thread_id)      # -> {"thread_id", "spans": [...], "totals": {...}} or None
#     for span in rec["spans"]:
#         print(span["layer"], span["tokens_in"], span["tokens_out"], span["latency_ms"], span["status"])

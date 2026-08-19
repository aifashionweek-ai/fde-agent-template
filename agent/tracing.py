"""Tracing (D-006, D-013). LangSmith is AI-native: it sees prompts, tool I/O, tokens, and the node PATH.

What we add on top of the default LangGraph→LangSmith integration:
  * run-level metadata (tenant, model profile, git sha, experiment) so traces are filterable/exportable
  * a node_span decorator that appends the node name to state.path → every result carries its own path
  * a helper to turn a trace into an eval row (closing the loop: prod trace → golden set)
Env: LANGSMITH_TRACING=true LANGSMITH_API_KEY=… LANGSMITH_PROJECT=fde-agent
"""
import os, functools, subprocess

def _sha() -> str:
    try: return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return "nogit"

def tag_run(**md) -> dict:
    """Returns a config fragment: {'metadata': {...}, 'tags': [...]} — LangSmith indexes both."""
    md = {"model_profile": os.getenv("MODEL_PROFILE") or os.getenv("LLM_PROVIDER", "anthropic"),
          "git_sha": _sha(), "experiment": os.getenv("EXPERIMENT", "live"), **md}
    return {"metadata": md, "tags": [f"tenant:{md.get('tenant','?')}", f"model:{md['model_profile']}"]}

def node_span(name: str):
    """Append node name to state.path; LangSmith already spans each node, this makes the path part of the OUTPUT."""
    def deco(fn):
        @functools.wraps(fn)
        def w(s, *a, **k):
            out = fn(s, *a, **k) or {}
            out.setdefault("path", s.get("path", []) + [name])
            return out
        return w
    return deco

def trace_to_eval_row(run_id: str, expected: str, tags: list[str]) -> dict:
    """Pull a LangSmith run and emit a dataset row — use after a human marks a prod run as good/bad."""
    from langsmith import Client
    r = Client().read_run(run_id)
    return {"input": (r.inputs or {}).get("task", ""), "expected": expected, "tags": tags, "source_run": run_id}

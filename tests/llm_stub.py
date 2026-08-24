"""Shared scripted LLM for graph-level integration tests (not collected — no test_ prefix).
Deterministic stand-in for the model: the graph, guards, authz, approval binding, tools, and the
checkpointer stay REAL. Planner prompt (str) -> a plan; act -> propose submit_action(alice) until a tool
result arrives, then emit a final JSON answer that ECHOES the last ToolMessage — so execution/refusal/
denial evidence is observable in the wire response."""
import json

from langchain_core.messages import AIMessage, ToolMessage


class ScriptedLLM:
    def bind_tools(self, tools):
        return self

    def invoke(self, input):
        if isinstance(input, str):                       # plan node
            return AIMessage(content='["do the requested step"]')
        last = input[-1]
        if isinstance(last, ToolMessage):                # act after tools/denial -> final answer
            return AIMessage(content=json.dumps({
                "answer": f"outcome: {last.content}", "confidence": 0.2, "citations": [], "actions": []}))
        return AIMessage(content="", tool_calls=[{      # act -> propose the side effect
            "name": "submit_action", "args": {"target": "alice", "detail": "x"},
            "id": "call_1", "type": "tool_call"}])

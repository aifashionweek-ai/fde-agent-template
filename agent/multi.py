"""Agent-to-agent: supervisor + specialist agents sharing typed state, handoff via Command.
Cross-process A2A: expose each agent as an HTTP endpoint with the same AgentOutput contract (see api/main.py)."""
from typing import Literal
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from .llm import get_llm

class TeamState(MessagesState):
    next: str

def supervisor(s: TeamState) -> Command[Literal["researcher","writer","__end__"]]:
    q = "Who should act next: researcher, writer, or FINISH? Answer one word.\n" + s["messages"][-1].content
    choice = get_llm().invoke(q).content.strip().lower()
    goto = "researcher" if "research" in choice else "writer" if "writ" in choice else END
    return Command(goto=goto, update={"next": str(goto)})

def researcher(s: TeamState) -> Command[Literal["supervisor"]]:
    r = get_llm().invoke([HumanMessage("Research facts for: " + s["messages"][0].content)])
    return Command(goto="supervisor", update={"messages": [HumanMessage(content=r.content, name="researcher")]})

def writer(s: TeamState) -> Command[Literal["supervisor"]]:
    r = get_llm().invoke(s["messages"] + [HumanMessage("Write the final answer. Say FINISH when done.")])
    return Command(goto="supervisor", update={"messages": [HumanMessage(content=r.content, name="writer")]})

def build_team():
    g = StateGraph(TeamState)
    for n, f in [("supervisor",supervisor),("researcher",researcher),("writer",writer)]: g.add_node(n, f)
    g.add_edge(START, "supervisor")
    return g.compile()

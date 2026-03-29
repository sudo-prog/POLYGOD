from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from mem0 import Memory
from py_clob_client.client import ClobClient
from typing import TypedDict
import subprocess

memory = Memory.from_config({"provider": "qdrant", "vector_store": {"url": "http://qdrant:6333"}})
clob = ClobClient(...)  # reuse the existing client from base code

class PaperMirror:
    def __init__(self): self.pnls = []
    def execute_shadow(self, order):
        self.pnls.append(0.05)
        return {"pnl": 0.05, "status": "paper_executed"}

paper = PaperMirror()
MODE = 0

class AgentState(TypedDict):
    mode: int
    market_data: dict
    decision: dict
    paper_pnl: float

def research_node(state: AgentState):
    dexter_insight = consult_dexter(f"Analyze impact on {state.get('market_data', {})}")
    memory.add(f"Research + Dexter: {dexter_insight}", agent_id="polygod")
    state["market_data"] = {"prob": 0.65}
    return state

def consult_dexter(query: str):
    try:
        result = subprocess.run(["bun", "run", "../dexter/start", "--query", query], capture_output=True, text=True, timeout=60)
        return result.stdout
    except:
        return "Dexter offline"

def mode_router(state: AgentState):
    if state["mode"] == 0: return "approve_node"
    if state["mode"] == 3: return "execute_node"
    return "risk_gate_node"

def approve_node(state: AgentState):
    state["decision"]["approved"] = True
    return state

def risk_gate_node(state: AgentState):
    return "execute_node"

def execute_node(state: AgentState):
    order = {"size": 100, "price": 0.65}
    paper.execute_shadow(order)
    if state["mode"] >= 2:
        clob.create_market_order(order)
    state["paper_pnl"] = paper.pnls[-1]
    memory.add(f"Executed in Mode {state['mode']}", agent_id="polygod")
    return state

def critic_node(state: AgentState):
    memory.add("Reflection: tighten Kelly on low liquidity", agent_id="polygod")
    return state

workflow = StateGraph(AgentState)
workflow.add_node("research", research_node)
workflow.add_node("router", mode_router)
workflow.add_node("approve", approve_node)
workflow.add_node("risk_gate", risk_gate_node)
workflow.add_node("execute", execute_node)
workflow.add_node("critic", critic_node)

workflow.set_entry_point("research")
workflow.add_edge("research", "router")
workflow.add_edge("approve", "execute")
workflow.add_edge("risk_gate", "execute")
workflow.add_edge("execute", "critic")
workflow.add_edge("critic", END)

rag_god_app = workflow.compile(checkpointer=MemorySaver())

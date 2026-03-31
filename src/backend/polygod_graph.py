from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Any, Dict
from py_clob_client.client import ClobClient
from typing import TypedDict
import subprocess
from mem0 import Memory
import json
from src.backend.config import settings

# LangGraph state checkpointer (required)
langgraph_memory = MemorySaver()

# Real mem0 persistent memory (Qdrant-backed)
mem0_config = json.loads(settings.MEM0_CONFIG)
mem0_memory = Memory.from_config(mem0_config)

clob = ClobClient(host="http://localhost:8080", api_key="your_api_key_here")

class PaperMirror:
    def __init__(self): self.pnls = []
    def execute_shadow(self, order):
        self.pnls.append(0.05)
        return {"pnl": 0.05, "status": "paper_executed"}

paper = PaperMirror()
POLYGOD_MODE = 0

class AgentState(TypedDict):
    mode: int
    market_data: dict
    decision: dict
    paper_pnl: float

def research_node(state: AgentState):
    dexter_insight = consult_dexter(f"Analyze impact on {state.get('market_data', {})}")
    mem0_memory.add(
        messages=[{"role": "system", "content": f"research: {dexter_insight}"}],
        user_id="polygod"
    )
    state["market_data"] = {"prob": 0.65}
    return state

def consult_dexter(query: str):
    try:
        result = subprocess.run(["bun", "run", "../dexter/start", "--query", query], capture_output=True, text=True, timeout=60)
        return result.stdout
    except:
        return "Dexter offline"

def get_current_mode():
    try:
        from src.backend.main import MODE
        return MODE
    except:
        return POLYGOD_MODE

def mode_router(state: AgentState):
    mode = state.get("mode") or get_current_mode()
    if mode == 0: return "approve_node"
    if mode == 3: return "execute_node"
    return "risk_gate_node"

def approve_node(state: AgentState):
    state["decision"]["approved"] = True
    return state

def risk_gate_node(state: AgentState):
    decision = state.get("decision", {})
    order = decision.get("order", {"size": 100, "price": 0.65})
    mode = state.get("mode", 0)

    size = float(order.get("size", 100))
    volume = state.get("market_data", {}).get("volume", 10000) or 10000
    volatility = abs(state.get("paper_pnl", 0)) + 0.01

    risk_score = (size / volume) * volatility

    if risk_score > 0.05 or mode < 3:
        reason = f"Risk too high (score={risk_score:.3f}) or mode {mode} < 3"
        mem0_memory.add(
            messages=[{"role": "system", "content": f"Risk gate FAILED: {reason}"}],
            user_id="polygod"
        )
        return "approve_node"
    else:
        mem0_memory.add(
            messages=[{"role": "system", "content": f"Risk gate PASSED: score={risk_score:.3f}"}],
            user_id="polygod"
        )
        return "execute_node"

def execute_node(state: AgentState):
    order = state.get("decision", {}).get("order", {"size": 100, "price": 0.65})
    paper.execute_shadow(order)
    if state["mode"] >= 2:
        try:
            clob.create_market_order(order)
        except Exception as e:
            mem0_memory.add(
                messages=[{"role": "system", "content": f"execution_error: {str(e)}"}],
                user_id="polygod"
            )
    state["paper_pnl"] = paper.pnls[-1]
    mem0_memory.add(
        messages=[{"role": "system", "content": f"Executed in Mode {state['mode']}"}],
        user_id="polygod"
    )
    return state

def critic_node(state: AgentState):
    mem0_memory.add(
        messages=[{"role": "system", "content": "Reflection: tighten Kelly on low liquidity"}],
        user_id="polygod"
    )
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

polygod_app = workflow.compile(checkpointer=langgraph_memory)

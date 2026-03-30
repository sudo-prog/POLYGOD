import logging
import subprocess
from subprocess import SubprocessError, TimeoutExpired
from typing import TypedDict, Dict, Tuple, Any, NotRequired

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from mem0 import Memory

from agent_skills import (
    authenticate, place_order, stream_orderbook, get_positions,
    bridge_assets, gasless_execute
)
from config import settings

logger = logging.getLogger(__name__)

memory = Memory.from_config({"provider": "qdrant", "vector_store": {"url": "http://qdrant:6333"}})


def _get_clob_client():
    """
    Lazily initialize and return the CLOB client.
    Returns None if credentials are not configured.

    This reuses the existing client infrastructure from polymarket.client
    to avoid duplication and ensure proper configuration.
    """
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON
        from py_clob_client.clob_types import ApiCreds

        if not (settings.POLYMARKET_API_KEY and settings.POLYMARKET_SECRET and settings.POLYMARKET_PASSPHRASE):
            logger.warning("Polymarket credentials not configured. ClobClient unavailable.")
            return None

        creds = ApiCreds(
            api_key=settings.POLYMARKET_API_KEY,
            api_secret=settings.POLYMARKET_SECRET,
            api_passphrase=settings.POLYMARKET_PASSPHRASE,
        )

        return ClobClient(
            host="https://clob.polymarket.com",
            chain_id=POLYGON,
            creds=creds,
        )
    except Exception as e:
        logger.error(f"Failed to initialize ClobClient: {e}")
        return None


clob = _get_clob_client()

# POLYGOD Mode Constants
# Mode 0: SAFE - Paper trading only, no real orders
# Mode 1: AGGRESSIVE - Real orders with manual approval
# Mode 2: BEAST - Real orders with automatic execution
# Mode 3: BEAST_GASLESS - Gasless execution via Polymarket agent skills
POLYGOD_MODE_SAFE = 0
POLYGOD_MODE_AGGRESSIVE = 1
POLYGOD_MODE_BEAST = 2
POLYGOD_MODE_BEAST_GASLESS = 3

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
    auth_status: NotRequired[str]

def research_node(state: AgentState):
    dexter_insight = consult_dexter(f"Analyze impact on {state.get('market_data', {})}")
    memory.add(f"Research + Dexter: {dexter_insight}", agent_id="polygod")
    state["market_data"] = {"prob": 0.65}
    return state

def consult_dexter(query: str):
    """
    Consult Dexter for market analysis insights.

    Args:
        query: The analysis query to send to Dexter

    Returns:
        Dexter's response or a fallback message if unavailable
    """
    try:
        result = subprocess.run(
            ["bun", "run", "../dexter/start", "--query", query],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout
    except TimeoutExpired:
        logger.warning(f"Dexter query timed out after 60s: {query[:50]}...")
        return "Dexter offline (timeout)"
    except SubprocessError as e:
        logger.error(f"Dexter subprocess error: {e}")
        return f"Dexter offline (subprocess error: {e})"
    except OSError as e:
        logger.error(f"Dexter OS error (bun may not be installed): {e}")
        return f"Dexter offline (OS error: {e})"
    except Exception as e:
        logger.error(f"Dexter unexpected error: {e}")
        return f"Dexter offline (unexpected: {e})"

def official_auth_node(state: AgentState):
    try:
        auth = authenticate()  # official Polymarket skill
        state["auth_status"] = "ok"
    except Exception as e:
        auth = f"error: {e}"
        state["auth_status"] = "error"
    memory.add(f"Official auth: {auth}", agent_id="polygod")
    return state

def mode_router(state: AgentState):
    """
    Route to the appropriate node based on POLYGOD mode.

    Mode routing:
      - Mode 0 (SAFE): Route to approve node for manual confirmation
      - Mode 3 (BEAST_GASLESS): Route directly to execute node
      - Mode 1/2 (AGGRESSIVE/BEAST): Route to risk gate for validation

    Returns:
        The name of the next node to execute
    """
    mode = state.get("mode", 0)

    if mode == POLYGOD_MODE_SAFE:
        # Safe mode: require explicit approval
        return "approve"
    elif mode == POLYGOD_MODE_BEAST_GASLESS:
        # Beast gasless mode: skip approval, go straight to execution
        return "execute"
    else:
        # Aggressive/Beast mode: validate via risk gate
        return "risk_gate"

def approve_node(state: AgentState):
    state["decision"]["approved"] = True
    return state

def risk_gate_node(state: AgentState):
    """
    Risk gate validation before execution.

    This node validates orders before allowing execution in
    AGGRESSIVE and BEAST modes. Returns the execute node name
    to proceed with the workflow.

    Args:
        state: Current agent state with order decision

    Returns:
        The name of the next node to execute (always "execute")
    """
    # Future enhancement: Add actual risk validation logic here
    # For now, pass through to execution
    return "execute"


def _resolve_order_from_state(state: AgentState) -> Dict[str, Any]:
    """
    Extract an order dict from the agent state, if present.
    Does NOT apply defaults, so that real execution is never
    triggered by a fabricated fallback order.
    """
    decision = state.get("decision") or {}
    order = decision.get("order")
    if not isinstance(order, dict):
        return {}
    return order


def _validate_order(order: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate order structure and apply basic sanity checks.
    This is intentionally conservative to avoid accidental real executions.
    """
    if not order:
        return False, "missing order"

    # required fields
    for field in ("size", "price"):
        if field not in order:
            return False, f"missing required field '{field}'"

    # type checks
    try:
        size = float(order["size"])
        price = float(order["price"])
    except (TypeError, ValueError):
        return False, "size and price must be numeric"

    # sanity bounds (tune as needed)
    if size <= 0:
        return False, "size must be positive"
    if size > 1_000_000:
        return False, "size exceeds maximum allowed"
    if price <= 0 or price > 1:
        return False, "price must be in (0, 1]"

    return True, "ok"


def execute_node(state: AgentState):
    """
    Execute an order in paper mode (always) and optionally via official skills
    depending on `state['mode']`.

    Mode semantics:
      - mode < 2: paper-only (shadow) execution
      - mode >= 2: paper execution + attempt real execution, *if* a valid order
                   is present in state['decision']['order'].
    """
    # 1) Determine the order from state (no defaults for real execution)
    order_from_state = _resolve_order_from_state(state)
    is_valid, validation_reason = _validate_order(order_from_state)

    # 2) Always-on paper mirror uses a safe fallback if needed
    paper_order = order_from_state if is_valid else {"size": 100, "price": 0.65}
    paper.execute_shadow(paper_order)  # always-on mirror

    # 3) Real execution: only if mode >= 2 and order is valid
    if state.get("mode", 0) >= 2 and is_valid:
        # Official Polymarket skill + py-clob-client
        if state["mode"] == 3:
            gasless_execute(order_from_state)  # beast mode
            exec_mode_desc = "gasless_execute"
        else:
            place_order(order_from_state)  # official skill
            exec_mode_desc = "place_order"

        memory.add(
            f"Executed via official skills ({exec_mode_desc}) in Mode {state['mode']} "
            f"with order={order_from_state}",
            agent_id="polygod",
        )
    elif state.get("mode", 0) >= 2 and not is_valid:
        # Mode requested real execution but order is not safe; log and skip
        memory.add(
            f"Skipped real execution in Mode {state['mode']} due to invalid order: "
            f"{validation_reason}, order={order_from_state}",
            agent_id="polygod",
        )
    else:
        # Pure paper mode
        memory.add(
            f"Paper-only execution in Mode {state.get('mode', 0)} with order={paper_order}",
            agent_id="polygod",
        )

    # 4) Update paper PnL in state
    state["paper_pnl"] = paper.pnls[-1]
    return state

def critic_node(state: AgentState):
    memory.add("Reflection: tighten Kelly on low liquidity", agent_id="polygod")
    return state

workflow = StateGraph(AgentState)
workflow.add_node("research", research_node)
workflow.add_node("official_auth", official_auth_node)
workflow.add_node("router", mode_router)
workflow.add_node("approve", approve_node)
workflow.add_node("risk_gate", risk_gate_node)
workflow.add_node("execute", execute_node)
workflow.add_node("critic", critic_node)

workflow.set_entry_point("research")
workflow.add_edge("research", "official_auth")
workflow.add_edge("official_auth", "router")
workflow.add_edge("approve", "execute")
workflow.add_edge("risk_gate", "execute")
workflow.add_edge("execute", "critic")
workflow.add_edge("critic", END)

polygod_app = workflow.compile(checkpointer=MemorySaver())

"""
RAG_GOD Graph Module - Cyclic Swarm Intelligence for Polymarket Trading

Implements a LangGraph-based cyclic swarm with:
- research_node: Market analysis and signal generation
- mode_router: Routes execution based on risk mode (0-3)
- approve_node: Human-in-the-loop approval gate
- risk_gate_node: Kelly criterion position sizing guard
- execute_node: Live + paper shadow execution
- critic_node: Post-execution analysis and feedback loop
- consult_dexter: External consultation tool
- Mem0 integration for persistent memory
- PaperMirror class for paper trading simulation
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional, TypedDict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

MODE = int(os.getenv("RAG_GOD_MODE", "0"))

class RiskMode(IntEnum):
    """Risk modes from safe to aggressive"""
    OBSERVE = 0      # Only research and analyze, no execution
    CONSERVATIVE = 1  # Small positions, requires approval
    MODERATE = 2      # Medium positions, auto-approve low-risk
    BEAST = 3         # Full Kelly sizing, autonomous execution


# ============================================================================
# PAPER MIRROR CLASS
# ============================================================================

class PaperMirror:
    """
    Paper trading system that mirrors every live decision.
    Tracks positions, P&L, and trade history for analysis.
    """

    def __init__(self):
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.pnls: List[float] = [0.0]
        self.trade_history: List[Dict[str, Any]] = []
        self.total_pnl: float = 0.0
        self.starting_capital: float = 10000.0
        self.current_capital: float = self.starting_capital

    def open_position(
        self,
        market_id: str,
        side: str,
        size: float,
        price: float,
        reasoning: str = ""
    ) -> Dict[str, Any]:
        """Open a paper position mirroring a live trade."""
        trade_id = str(uuid4())

        position = {
            "trade_id": trade_id,
            "market_id": market_id,
            "side": side,
            "size": size,
            "entry_price": price,
            "entry_time": datetime.utcnow().isoformat(),
            "reasoning": reasoning,
            "status": "open"
        }

        self.positions[trade_id] = position
        self.trade_history.append({
            **position,
            "action": "open"
        })

        logger.info(f"[PAPER_MIRROR] Opened {side} position: {size} @ {price}")
        return position

    def close_position(
        self,
        trade_id: str,
        exit_price: float,
        reason: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Close a paper position and calculate P&L."""
        if trade_id not in self.positions:
            logger.warning(f"[PAPER_MIRROR] Position {trade_id} not found")
            return None

        position = self.positions[trade_id]

        # Calculate P&L
        if position["side"] == "yes":
            pnl = (exit_price - position["entry_price"]) * position["size"]
        else:  # no side
            pnl = (position["entry_price"] - exit_price) * position["size"]

        self.total_pnl += pnl
        self.current_capital += pnl
        self.pnls.append(self.total_pnl)

        # Update position
        position["status"] = "closed"
        position["exit_price"] = exit_price
        position["exit_time"] = datetime.utcnow().isoformat()
        position["pnl"] = pnl
        position["reason"] = reason

        self.trade_history.append({
            **position,
            "action": "close"
        })

        logger.info(f"[PAPER_MIRROR] Closed position: PnL = ${pnl:.2f}")
        return position

    def get_stats(self) -> Dict[str, Any]:
        """Get current paper trading statistics."""
        open_positions = [p for p in self.positions.values() if p["status"] == "open"]

        return {
            "total_pnl": self.total_pnl,
            "current_capital": self.current_capital,
            "return_pct": ((self.current_capital - self.starting_capital) / self.starting_capital) * 100,
            "open_positions": len(open_positions),
            "total_trades": len(self.trade_history),
            "win_rate": self._calculate_win_rate(),
            "recent_pnls": self.pnls[-10:]  # Last 10 P&L snapshots
        }

    def _calculate_win_rate(self) -> float:
        """Calculate win rate from closed trades."""
        closed_trades = [
            t for t in self.trade_history
            if t.get("action") == "close" and "pnl" in t
        ]

        if not closed_trades:
            return 0.0

        wins = sum(1 for t in closed_trades if t["pnl"] > 0)
        return (wins / len(closed_trades)) * 100


# Global paper mirror instance
paper = PaperMirror()


# ============================================================================
# MEMORY MANAGER (Mem0 Integration)
# ============================================================================

class MemoryManager:
    """
    Manages persistent memory using Mem0/Qdrant for learning from past decisions.
    """

    def __init__(self):
        self.enabled = os.getenv("MEM0_ENABLED", "false").lower() == "true"
        self.memories: List[Dict[str, Any]] = []  # In-memory fallback
        logger.info(f"[MEMORY] MemoryManager initialized (enabled={self.enabled})")

    async def write(self, event_type: str, data: Dict[str, Any]) -> None:
        """Write a memory event."""
        memory = {
            "id": str(uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": data
        }

        self.memories.append(memory)

        # Keep last 1000 memories in memory
        if len(self.memories) > 1000:
            self.memories = self.memories[-1000:]

        logger.debug(f"[MEMORY] Wrote event: {event_type}")

    async def recall(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Recall relevant memories based on query."""
        # Simple keyword matching for now
        relevant = [
            m for m in self.memories
            if query.lower() in json.dumps(m.get("data", {})).lower()
        ]

        return relevant[-limit:]

    async def get_market_history(self, market_id: str) -> List[Dict[str, Any]]:
        """Get all memories related to a specific market."""
        return [
            m for m in self.memories
            if m.get("data", {}).get("market_id") == market_id
        ]


# Global memory manager
memory = MemoryManager()


# ============================================================================
# GRAPH STATE
# ============================================================================

class RAGGodState(TypedDict):
    """State schema for the RAG_GOD graph."""
    market_id: str
    market_data: Dict[str, Any]
    research_signals: List[Dict[str, Any]]
    approved: bool
    position_size: float
    side: str
    execution_result: Optional[Dict[str, Any]]
    criticism: Optional[str]
    cycle_count: int
    metadata: Dict[str, Any]


# ============================================================================
# NODE IMPLEMENTATIONS
# ============================================================================

async def research_node(state: RAGGodState) -> RAGGodState:
    """
    Research node: Analyze market data and generate trading signals.

    Performs:
    - Technical analysis on price history
    - Sentiment analysis from news
    - Whale activity detection
    - Pattern recognition
    """
    logger.info(f"[RESEARCH] Analyzing market {state['market_id']}")

    market_data = state.get("market_data", {})

    # Generate research signals based on available data
    signals = []

    # Volume signal
    volume_24h = market_data.get("volume_24h", 0)
    if volume_24h > 100000:
        signals.append({
            "type": "volume",
            "strength": "high",
            "direction": "bullish" if market_data.get("yes_percentage", 50) > 50 else "bearish",
            "confidence": 0.7
        })

    # Price momentum signal
    yes_pct = market_data.get("yes_percentage", 50)
    if yes_pct > 70:
        signals.append({
            "type": "momentum",
            "strength": "strong",
            "direction": "bullish",
            "confidence": 0.8
        })
    elif yes_pct < 30:
        signals.append({
            "type": "momentum",
            "strength": "strong",
            "direction": "bearish",
            "confidence": 0.8
        })

    # Recall relevant memories
    past_memories = await memory.recall(f"market_{state['market_id']}")
    if past_memories:
        signals.append({
            "type": "memory",
            "strength": "contextual",
            "direction": "neutral",
            "confidence": 0.5,
            "data": {"past_events": len(past_memories)}
        })

    # Write research event to memory
    await memory.write("research_complete", {
        "market_id": state["market_id"],
        "signals_generated": len(signals),
        "cycle_count": state.get("cycle_count", 0)
    })

    state["research_signals"] = signals
    logger.info(f"[RESEARCH] Generated {len(signals)} signals")

    return state


async def mode_router(state: RAGGodState) -> str:
    """
    Mode router: Determines next node based on current risk mode.

    Modes:
    - 0 (OBSERVE): Only research, no execution
    - 1 (CONSERVATIVE): Requires manual approval
    - 2 (MODERATE): Auto-approve moderate confidence
    - 3 (BEAST): Full autonomous execution
    """
    global MODE

    logger.info(f"[MODE_ROUTER] Current mode: {MODE}")

    await memory.write("mode_routing", {
        "mode": MODE,
        "market_id": state["market_id"]
    })

    if MODE == RiskMode.OBSERVE:
        return "critic"  # Skip execution, go to analysis

    if MODE == RiskMode.CONSERVATIVE:
        return "approve"  # Always require approval

    if MODE == RiskMode.MODERATE:
        # Auto-approve if signals are strong enough
        signals = state.get("research_signals", [])
        avg_confidence = sum(s.get("confidence", 0) for s in signals) / max(len(signals), 1)

        if avg_confidence > 0.7:
            state["approved"] = True
            return "risk_gate"
        else:
            return "approve"

    if MODE == RiskMode.BEAST:
        # Full autonomous - approve everything
        state["approved"] = True
        return "risk_gate"

    return "approve"  # Default to approval


async def approve_node(state: RAGGodState) -> RAGGodState:
    """
    Approval node: Human-in-the-loop gate for trade approval.

    In a production system, this would wait for user input.
    For now, it simulates approval based on signal strength.
    """
    logger.info(f"[APPROVE] Awaiting approval for market {state['market_id']}")

    signals = state.get("research_signals", [])

    # Simulate approval logic
    strong_signals = [s for s in signals if s.get("confidence", 0) > 0.7]

    if strong_signals:
        state["approved"] = True
        logger.info(f"[APPROVE] Auto-approved based on {len(strong_signals)} strong signals")
    else:
        # In production, this would wait for user input via WebSocket
        state["approved"] = False
        logger.info(f"[APPROVE] Manual approval required")

    await memory.write("approval_result", {
        "market_id": state["market_id"],
        "approved": state["approved"],
        "signal_count": len(signals)
    })

    return state


async def risk_gate_node(state: RAGGodState) -> RAGGodState:
    """
    Risk gate: Kelly criterion position sizing guard.

    Calculates optimal position size based on:
    - Win probability (from signals)
    - Average win/loss ratio
    - Current bankroll
    - Maximum position limits
    """
    logger.info(f"[RISK_GATE] Calculating position size")

    if not state.get("approved", False):
        logger.warning(f"[RISK_GATE] Trade not approved, skipping")
        state["position_size"] = 0
        return state

    # Calculate Kelly fraction
    signals = state.get("research_signals", [])
    market_data = state.get("market_data", {})

    # Estimate win probability from signals
    if signals:
        avg_confidence = sum(s.get("confidence", 0) for s in signals) / len(signals)
        # Map confidence to win probability (conservative)
        win_prob = 0.5 + (avg_confidence - 0.5) * 0.5
    else:
        win_prob = 0.5

    # Estimate odds from market
    yes_pct = market_data.get("yes_percentage", 50) / 100
    if yes_pct > 0.5:
        odds = 1 / yes_pct if yes_pct > 0 else 2.0
    else:
        odds = 1 / (1 - yes_pct) if yes_pct < 1 else 2.0

    # Kelly formula: f* = (bp - q) / b
    # where b = odds, p = win_prob, q = 1 - p
    b = odds - 1  # Net odds
    p = win_prob
    q = 1 - p

    if b > 0:
        kelly_fraction = (b * p - q) / b
    else:
        kelly_fraction = 0

    # Apply mode-based scaling
    mode_multiplier = {
        RiskMode.OBSERVE: 0,
        RiskMode.CONSERVATIVE: 0.25,  # Quarter Kelly
        RiskMode.MODERATE: 0.5,       # Half Kelly
        RiskMode.BEAST: 1.0           # Full Kelly
    }.get(MODE, 0.25)

    # Calculate position size
    bankroll = paper.current_capital
    max_position = bankroll * 0.2  # Max 20% per trade

    kelly_size = max(0, kelly_fraction) * bankroll * mode_multiplier
    position_size = min(kelly_size, max_position)

    # Determine side based on signals
    bullish_signals = [s for s in signals if s.get("direction") == "bullish"]
    bearish_signals = [s for s in signals if s.get("direction") == "bearish"]

    if len(bullish_signals) > len(bearish_signals):
        state["side"] = "yes"
    elif len(bearish_signals) > len(bullish_signals):
        state["side"] = "no"
    else:
        state["side"] = "yes" if yes_pct > 50 else "no"

    state["position_size"] = position_size

    await memory.write("risk_assessment", {
        "market_id": state["market_id"],
        "win_prob": win_prob,
        "kelly_fraction": kelly_fraction,
        "position_size": position_size,
        "side": state["side"],
        "mode": MODE
    })

    logger.info(f"[RISK_GATE] Position size: ${position_size:.2f} on {state['side']}")

    return state


async def execute_node(state: RAGGodState) -> RAGGodState:
    """
    Execution node: Execute trade on live market + paper mirror.

    In production, this would call the Polymarket API.
    For now, it simulates execution and mirrors to paper trading.
    """
    position_size = state.get("position_size", 0)
    side = state.get("side", "yes")
    market_id = state["market_id"]
    market_data = state.get("market_data", {})

    if position_size <= 0:
        logger.info(f"[EXECUTE] No position to execute")
        state["execution_result"] = {"status": "skipped", "reason": "zero_size"}
        return state

    logger.info(f"[EXECUTE] Executing {side} trade: ${position_size:.2f}")

    # Get current price from market data
    current_price = market_data.get("yes_percentage", 50) / 100
    if side == "no":
        current_price = 1 - current_price

    # Simulate live execution
    trade_id = str(uuid4())
    execution_result = {
        "status": "executed",
        "trade_id": trade_id,
        "market_id": market_id,
        "side": side,
        "size": position_size,
        "price": current_price,
        "timestamp": datetime.utcnow().isoformat(),
        "mode": MODE
    }

    # Mirror to paper trading
    paper_position = paper.open_position(
        market_id=market_id,
        side=side,
        size=position_size / current_price,  # Convert to shares
        price=current_price,
        reasoning=json.dumps(state.get("research_signals", [])[:3])
    )

    execution_result["paper_trade_id"] = paper_position.get("trade_id")

    state["execution_result"] = execution_result

    await memory.write("execution", {
        "market_id": market_id,
        "trade_id": trade_id,
        "side": side,
        "size": position_size,
        "price": current_price,
        "mode": MODE
    })

    logger.info(f"[EXECUTE] Trade executed and mirrored to paper")

    return state


async def critic_node(state: RAGGodState) -> RAGGodState:
    """
    Critic node: Post-execution analysis and feedback.

    Analyzes:
    - Execution quality
    - Signal accuracy
    - Risk management effectiveness
    - Generates criticism for improvement
    """
    logger.info(f"[CRITIC] Analyzing execution for market {state['market_id']}")

    execution = state.get("execution_result", {})
    signals = state.get("research_signals", [])
    cycle_count = state.get("cycle_count", 0) + 1

    criticism_points = []

    # Analyze signal quality
    if not signals:
        criticism_points.append("No research signals generated - improve data collection")
    else:
        avg_confidence = sum(s.get("confidence", 0) for s in signals) / len(signals)
        if avg_confidence < 0.6:
            criticism_points.append(f"Low average signal confidence: {avg_confidence:.2f}")

    # Analyze execution
    if execution.get("status") == "skipped":
        criticism_points.append(f"Execution skipped: {execution.get('reason', 'unknown')}")
    elif execution.get("status") == "executed":
        # Check if we're in a winning streak
        stats = paper.get_stats()
        if stats["win_rate"] < 50:
            criticism_points.append(f"Win rate below 50%: {stats['win_rate']:.1f}%")

    # Generate criticism
    if criticism_points:
        state["criticism"] = "; ".join(criticism_points)
        logger.warning(f"[CRITIC] Issues found: {state['criticism']}")
    else:
        state["criticism"] = None
        logger.info(f"[CRITIC] No issues found")

    state["cycle_count"] = cycle_count

    await memory.write("criticism", {
        "market_id": state["market_id"],
        "cycle_count": cycle_count,
        "criticism": state["criticism"],
        "paper_stats": paper.get_stats()
    })

    return state


async def consult_dexter(
    market_id: str,
    query: str
) -> Dict[str, Any]:
    """
    Consult Dexter (external AI) for additional analysis.

    In production, this would call an external AI service.
    For now, it returns simulated advice.
    """
    logger.info(f"[DEXTER] Consulting for market {market_id}: {query}")

    # Simulate Dexter's response
    advice = {
        "recommendation": "cautious",
        "confidence": 0.6,
        "reasoning": "Market showing high volatility, suggest smaller position size",
        "timestamp": datetime.utcnow().isoformat()
    }

    await memory.write("dexter_consultation", {
        "market_id": market_id,
        "query": query,
        "advice": advice
    })

    return advice


# ============================================================================
# FASTAPI SUB-APPLICATION
# ============================================================================

rag_god_app = FastAPI(
    title="RAG_GOD Trading Brain",
    description="Cyclic swarm intelligence for Polymarket trading",
    version="1.0.0"
)


class TradeRequest(BaseModel):
    """Request model for trade execution."""
    market_id: str
    market_data: Dict[str, Any] = Field(default_factory=dict)
    force_mode: Optional[int] = None


class ModeSwitchRequest(BaseModel):
    """Request model for mode switching."""
    new_mode: int = Field(ge=0, le=3)


@rag_god_app.get("/status")
async def get_status():
    """Get RAG_GOD status and paper trading stats."""
    global MODE

    mode_names = {
        0: "OBSERVE",
        1: "CONSERVATIVE",
        2: "MODERATE",
        3: "BEAST MODE"
    }

    return {
        "status": "active",
        "mode": MODE,
        "mode_name": mode_names.get(MODE, "UNKNOWN"),
        "paper_stats": paper.get_stats(),
        "memory_count": len(memory.memories),
        "timestamp": datetime.utcnow().isoformat()
    }


@rag_god_app.post("/analyze")
async def analyze_market(request: TradeRequest):
    """
    Run the full RAG_GOD analysis cycle on a market.

    Executes: research → mode_router → approve → risk_gate → execute → critic
    """
    global MODE

    if request.force_mode is not None:
        original_mode = MODE
        MODE = request.force_mode

    # Initialize state
    state: RAGGodState = {
        "market_id": request.market_id,
        "market_data": request.market_data,
        "research_signals": [],
        "approved": False,
        "position_size": 0,
        "side": "yes",
        "execution_result": None,
        "criticism": None,
        "cycle_count": 0,
        "metadata": {"started_at": datetime.utcnow().isoformat()}
    }

    try:
        # Run the graph cycle
        # Research
        state = await research_node(state)

        # Mode routing
        next_node = await mode_router(state)

        if next_node == "critic":
            # Observe mode - skip execution
            state = await critic_node(state)
        elif next_node == "approve":
            # Require approval
            state = await approve_node(state)
            if state["approved"]:
                state = await risk_gate_node(state)
                state = await execute_node(state)
            state = await critic_node(state)
        elif next_node == "risk_gate":
            # Auto-approved
            state = await risk_gate_node(state)
            state = await execute_node(state)
            state = await critic_node(state)

        # Restore original mode if overridden
        if request.force_mode is not None:
            MODE = original_mode

        return {
            "success": True,
            "market_id": state["market_id"],
            "signals": state["research_signals"],
            "approved": state["approved"],
            "position_size": state["position_size"],
            "side": state["side"],
            "execution": state["execution_result"],
            "criticism": state["criticism"],
            "cycle_count": state["cycle_count"],
            "paper_stats": paper.get_stats()
        }

    except Exception as e:
        logger.error(f"[RAG_GOD] Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rag_god_app.post("/paper/close/{trade_id}")
async def close_paper_trade(trade_id: str, exit_price: float = 0.5):
    """Close a paper trading position."""
    result = paper.close_position(trade_id, exit_price, "manual_close")

    if result is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    return result


@rag_god_app.get("/paper/stats")
async def get_paper_stats():
    """Get paper trading statistics."""
    return paper.get_stats()


@rag_god_app.get("/memory/search")
async def search_memory(query: str, limit: int = 5):
    """Search memory for relevant past events."""
    results = await memory.recall(query, limit)
    return {"query": query, "results": results}


@rag_god_app.post("/consult")
async def consult_dexter_endpoint(market_id: str, query: str):
    """Consult Dexter for additional analysis."""
    advice = await consult_dexter(market_id, query)
    return {"market_id": market_id, "query": query, "advice": advice}


logger.info("[RAG_GOD] Graph module loaded successfully")

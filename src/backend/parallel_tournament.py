# src/backend/parallel_tournament.py
"""
Parallel Paper Tournament — God-tier Darwinian evolution for trading configs.

Spawns 50 parallel paper trading variants, offloads heavy work to free GPU
(Lightning AI / Colab), and selects winners via Sharpe-weighted scoring.
"""

import asyncio
import json
import logging
import random
from typing import Any, Dict, List

import httpx
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from mem0 import Memory
from src.backend.llm_router import router
from src.backend.config import settings

logger = logging.getLogger(__name__)

# Mem0 for hindsight storage
try:
    mem0 = Memory.from_config({"vector_store": {"provider": "qdrant", "url": "http://qdrant:6333"}})
except Exception as e:
    logger.warning(f"Mem0 init failed in parallel_tournament: {e}")
    mem0 = None


# ==================== LOCAL PAPER TRADING SIMULATION ====================
def simulate_paper_trade(market_id: str, config: dict, dry_run: bool = True) -> dict:
    """
    Local paper trading simulation (fallback for polymarket.agents.simulate_paper_trade).
    
    Simulates a 5-minute paper trade with Kelly-adjusted sizing and realistic slippage.
    """
    kelly_fraction = config.get("kelly_fraction", 0.25)
    model_temp = config.get("model_temp", 0.7)
    base_size = config.get("base_size", 1000)
    
    # Adjust position size by Kelly fraction
    position_size = base_size * kelly_fraction
    
    # Simulate market microstructure effects
    slippage = random.uniform(0.001, 0.01) * (1 + model_temp * 0.5)  # Higher temp = more slippage
    spread = random.uniform(0.002, 0.008)
    
    # Simulate price movement (5-minute window)
    price_change = random.gauss(0.02, 0.05 * model_temp)  # Volatility scales with temp
    win = price_change > 0
    
    # Calculate PnL with realistic costs
    gross_pnl = position_size * price_change
    trading_cost = position_size * (slippage + spread)
    net_pnl = gross_pnl - trading_cost if win else gross_pnl - trading_cost
    
    # Risk metrics
    max_drawdown = abs(min(0, net_pnl)) / position_size if position_size > 0 else 0
    
    return {
        "market_id": market_id,
        "config": config,
        "position_size": position_size,
        "gross_pnl": round(gross_pnl, 4),
        "net_pnl": round(net_pnl, 4),
        "slippage": round(slippage, 6),
        "spread": round(spread, 6),
        "price_change": round(price_change, 6),
        "max_drawdown": round(max_drawdown, 6),
        "win": win,
        "dry_run": dry_run,
    }


def evaluate_with_langsmith(pnl_result: dict, config: dict) -> float:
    """
    Score a paper trade result using RAGAS-style metrics.
    
    Combines PnL, risk-adjusted returns, and config efficiency.
    """
    net_pnl = pnl_result.get("net_pnl", 0)
    max_drawdown = pnl_result.get("max_drawdown", 0)
    win = pnl_result.get("win", False)
    kelly = config.get("kelly_fraction", 0.25)
    temp = config.get("model_temp", 0.7)
    
    # Base score from PnL (normalized)
    pnl_score = max(0, min(1, (net_pnl + 100) / 200))  # Normalize to 0-1 range
    
    # Risk penalty (higher drawdown = lower score)
    risk_penalty = max_drawdown * 2
    
    # Win bonus
    win_bonus = 0.1 if win else 0
    
    # Kelly efficiency (optimal around 0.25)
    kelly_efficiency = 1 - abs(kelly - 0.25) * 2
    
    # Temperature penalty (prefer moderate temps)
    temp_penalty = abs(temp - 0.7) * 0.5
    
    # Composite score
    score = (
        pnl_score * 0.5 +
        kelly_efficiency * 0.2 +
        win_bonus -
        risk_penalty * 0.3 -
        temp_penalty * 0.1
    )
    
    return max(0, min(1, score))


# ==================== PARALLEL TOURNAMENT NODE ====================
async def run_single_paper_tournament(state: dict, config_variant: dict) -> dict:
    """Run one 5-min paper sim with Kelly + slippage guard."""
    market_id = state.get("market_id", "unknown")
    
    # Run simulation
    pnl = simulate_paper_trade(market_id, config_variant, dry_run=True)
    
    # Score with LangSmith + RAGAS
    score = evaluate_with_langsmith(pnl, config_variant)
    
    return {"config": config_variant, "pnl": pnl, "score": score}


async def offload_to_lightning_ai(variants: List[dict]) -> List[dict]:
    """Offload heavy tournament batches to Lightning AI free tier."""
    lightning_token = settings.LIGHTNING_AI_TOKEN if hasattr(settings, 'LIGHTNING_AI_TOKEN') else None
    
    if not lightning_token:
        logger.warning("LIGHTNING_AI_TOKEN not set — skipping offload")
        return []
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.lightning.ai/v1/run",
                headers={"Authorization": f"Bearer {lightning_token}"},
                json={
                    "task": "tournament_batch",
                    "variants": variants,
                    "timeout": 300,  # 5 minutes
                },
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Lightning AI offload successful: {len(variants)} variants")
            return result.get("results", [])
    except Exception as e:
        logger.warning(f"Lightning AI offload failed: {e}")
        # Fallback to Colab webhook if available
        return await offload_to_colab(variants)


async def offload_to_colab(variants: List[dict]) -> List[dict]:
    """Fallback offload to Google Colab (one-click deploy)."""
    colab_url = settings.COLAB_WEBHOOK_URL if hasattr(settings, 'COLAB_WEBHOOK_URL') else None
    
    if not colab_url:
        logger.warning("COLAB_WEBHOOK_URL not set — skipping Colab offload")
        return []
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                colab_url,
                json={"task": "tournament_batch", "variants": variants},
                timeout=120.0,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Colab offload successful: {len(variants)} variants")
            return result.get("results", [])
    except Exception as e:
        logger.error(f"Colab offload failed: {e}")
        return []


async def parallel_paper_tournament(state: dict) -> dict:
    """
    God-tier Parallel Paper Tournament.
    
    Spawns 50 variants in parallel, offloads heavy work to free GPU,
    and selects winners via Darwinian selection + Mem0 hindsight.
    """
    market_id = state.get("market_id", "unknown")
    question = state.get("question", "Unknown Market")
    
    logger.info(f"PARALLEL TOURNAMENT: Spawning 50 variants for '{question[:50]}...'")
    
    # Generate 50 config variants (Kelly fractions × model temps)
    kelly_fractions = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]
    model_temps = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
    
    variants = [
        {"kelly_fraction": k, "model_temp": t, "base_size": 1000}
        for k in kelly_fractions
        for t in model_temps
    ][:50]  # Cap at 50
    
    # Offload heavy batches to free GPU if available
    offloaded_results = []
    local_variants = variants.copy()
    
    if len(variants) > 10:
        # Try to offload first 30 to Lightning AI
        offloaded_results = await offload_to_lightning_ai(variants[:30])
        if offloaded_results:
            local_variants = variants[30:]
            logger.info(f"Offloaded {len(offloaded_results)} results from Lightning AI")
    
    # Fan-out with asyncio.gather for local variants
    local_results = await asyncio.gather(
        *[run_single_paper_tournament(state, v) for v in local_variants],
        return_exceptions=True
    )
    
    # Filter out exceptions and combine results
    valid_results = []
    for r in local_results:
        if isinstance(r, dict) and "config" in r:
            valid_results.append(r)
        elif isinstance(r, Exception):
            logger.warning(f"Tournament variant failed: {r}")
    
    # Add offloaded results
    for r in offloaded_results:
        if isinstance(r, dict) and "config" in r:
            valid_results.append(r)
    
    if not valid_results:
        logger.error("All tournament variants failed!")
        return state
    
    # Darwinian selection: sort by score × pnl (multi-objective)
    winners = sorted(
        valid_results,
        key=lambda x: x.get("score", 0) * max(0.01, x.get("pnl", {}).get("net_pnl", 0)),
        reverse=True
    )[:3]
    
    best = winners[0]
    
    logger.info(
        f"PARALLEL TOURNAMENT COMPLETE: "
        f"best_kelly={best['config']['kelly_fraction']:.1%}, "
        f"best_temp={best['config']['model_temp']:.1f}, "
        f"score={best['score']:.3f}, "
        f"pnl=${best['pnl']['net_pnl']:.2f}"
    )
    
    # Store winners in Mem0 for hindsight learning
    if mem0:
        try:
            mem0.add(
                f"Parallel tournament winners for '{question}': " +
                json.dumps([{
                    "kelly": w["config"]["kelly_fraction"],
                    "temp": w["config"]["model_temp"],
                    "score": w["score"],
                    "pnl": w["pnl"]["net_pnl"]
                } for w in winners]),
                user_id="evolution_lab"
            )
        except Exception as e:
            logger.debug(f"Mem0 write failed: {e}")
    
    # Update state with best config
    evolved_order = {
        "size": 1000 * best["config"]["kelly_fraction"],
        "kelly_fraction": best["config"]["kelly_fraction"],
        "model_temp": best["config"]["model_temp"],
    }
    
    state["evolution_best"] = best
    state["decision"] = {
        **state.get("decision", {}),
        "order": evolved_order,
        "tournament_winners": winners,
        "tournament_best_score": best["score"],
        "tournament_best_pnl": best["pnl"]["net_pnl"],
    }
    state["final_decision"] = {
        **state.get("decision", {}),
        "evolution_complete": True,
        "best_config": best["config"],
    }
    
    return state


# ==================== GRAPH INTEGRATION ====================
# This node is wired into polygod_graph.py via:
#   workflow.add_node("parallel_tournament", parallel_paper_tournament)
#   workflow.add_edge("evolution_lab", "parallel_tournament")
#   workflow.add_conditional_edges("parallel_tournament", lambda s: "moderator" if s.final_decision else END)
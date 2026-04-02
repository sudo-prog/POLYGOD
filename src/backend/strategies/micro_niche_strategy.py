# src/backend/strategies/micro_niche_strategy.py
"""
Micro-Niche Trading Strategy — Karpathy Agent Editable

This file is mutated by the AutoResearch Lab (Karpathy loop).
The LLM agent proposes targeted edits BELOW the # MUTATION_POINT marker.
After each mutation, a parallel paper tournament tests 50 variants.
Winners (Sharpe > 2.0, PnL > 0) are kept; losers are git-reset.

Mutation protocol:
1. Only modify parameters/rules below # MUTATION_POINT
2. One focused change per mutation
3. Tournament validates before promotion to main swarm
"""

# ============================================================
# IMMUTABLE HEADER — Do not edit above this line
# ============================================================

# MUTATION_POINT — Karpathy agent will edit everything below this line
# Current mutation target: Kelly fraction, hedge thresholds, niche rules

# --- Position Sizing ---
KELLY_FRACTION = 0.02  # Fraction of Kelly to use (conservative: 0.02 = 2%)
MAX_POSITION_PCT = 0.15  # Max portfolio % per single position
MIN_POSITION_SIZE = 50  # Minimum trade size in USD

# --- Hedge & Risk Thresholds ---
HEDGE_THRESHOLD = 0.95  # Auto-hedge when correlation exceeds this
STOP_LOSS_PCT = 0.10  # Exit position at 10% loss
TAKE_PROFIT_PCT = 0.25  # Take profits at 25% gain

# --- Micro-Niche Detection ---
MIN_VOLUME_7D = 10000  # Minimum 7-day volume to consider (USD)
MAX_LIQUIDITY_RATIO = 5.0  # Max volume/liquidity ratio (detects thin markets)
MIN_MARKET_DEPTH = 500  # Minimum required depth on both sides (USD)

# --- Sentiment & Signal Weights ---
SENTIMENT_WEIGHT = 0.3  # Weight of X/Twitter sentiment in probability
POLYMARKET_WEIGHT = 0.5  # Weight of Polymarket price signal
NLP_WEIGHT = 0.2  # Weight of NLP/news sentiment

# --- Niche Category Thresholds ---
WEATHER_NICHE_MIN_VOL = 5000  # Weather markets: lower volume threshold
POLITICS_NICHE_MIN_VOL = 20000  # Politics markets: higher volume needed
CRYPTO_NICHE_MIN_VOL = 15000  # Crypto markets: medium volume threshold
TWITTER_TREND_MIN_VOL = 3000  # Twitter trend markets: very low volume ok

# --- Tournament Parameters ---
TOURNAMENT_SIMS = 200  # Simulations per variant in tournament
SHARPE_LOOKBACK = 50  # Period for Sharpe calculation (days)
EVOLUTION_MUTATION_RATE = 0.1  # Probability of mutation per generation


# --- Edge Detection Rules ---
def is_niche_opportunity(market_data: dict) -> bool:
    """Detect if a market qualifies as a micro-niche opportunity."""
    vol_7d = market_data.get("volume_7d", 0) or market_data.get("volume", 0)
    liquidity = market_data.get("liquidity", 0)
    prob = market_data.get("prob", 0.5) or market_data.get("yes_percentage", 50) / 100

    # Volume filter
    if vol_7d < MIN_VOLUME_7D:
        return False

    # Liquidity filter (avoid illiquid traps)
    if liquidity > 0 and (vol_7d / liquidity) > MAX_LIQUIDITY_RATIO:
        return False

    # Probability edge filter (look for mispriced markets)
    edge_threshold = 0.05  # 5% minimum deviation from 50/50
    if abs(prob - 0.5) < edge_threshold:
        return False

    return True


def calculate_position_size(market_data: dict, confidence: float) -> float:
    """Calculate position size based on Kelly + confidence."""
    base_size = market_data.get("target_size", 1000)
    prob = market_data.get("prob", 0.5) or 0.5

    # Kelly-adjusted size
    kelly_pct = KELLY_FRACTION * ((prob - 0.5) / 0.5) if prob != 0.5 else 0

    # Scale by confidence (0-1)
    position = base_size * max(kelly_pct, MIN_POSITION_SIZE / base_size) * confidence

    # Apply caps
    position = min(position, base_size * MAX_POSITION_PCT)
    position = max(position, MIN_POSITION_SIZE)

    return float(round(position, 2))

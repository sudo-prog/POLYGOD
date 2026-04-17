# SKILL: MARKET_INTELLIGENCE

Real-time edge detection. Run this protocol before any trade recommendation.

## EDGE DETECTION PROTOCOL

### Step 1: Price vs True Probability Gap
```python
# Load price history
history_7d = await fetch_price_history_from_clob(token_id, "7d", 60)
prices = [h["p"] * 100 for h in history_7d]

# Your estimate vs market price
market_price = prices[-1]  # current
your_estimate = ???  # from debate verdict

edge = abs(your_estimate - market_price)
ev_positive = (your_estimate > market_price and market_price < 50) or \
              (your_estimate < market_price and market_price > 50)

# Rule: only act if edge > 5% AND EV positive
```

### Step 2: Liquidity Check
```python
# NEVER enter a market where you'd move the price
order_book = await polymarket_client.get_order_book(market_id)
available_liquidity = sum(
    float(level.get("price",0)) * float(level.get("size",0))
    for level in order_book.get("asks", [])[:5]
)
# Rule: your_order_size < 5% of available_liquidity
```

### Step 3: Volume Trend (is money flowing in?)
```python
# Increasing volume = market is being repriced = dangerous
vol_24h = market_data["volume_24h"]
vol_7d_daily_avg = market_data["volume_7d"] / 7
volume_trend = vol_24h / vol_7d_daily_avg  # > 2 = unusual activity
# Rule: avoid entering when volume_trend > 3x (smart money is already in)
```

### Step 4: Resolution Date Check (CRITICAL)
```python
from src.backend.agents.debate import calculate_time_decay_metrics
metrics = calculate_time_decay_metrics(str(market_data["end_date"]), current_price)
days_left = metrics.get("days_remaining", 999)

# Rules:
# < 1 day: only enter if >95% confident (gamma risk)
# 1-3 days: need >85% confidence
# 3-7 days: need >75% confidence
# > 30 days: standard 65% threshold applies
```

### Step 5: Whale Confirmation
```python
fills = await polymarket_client.get_recent_fills(market_id, limit=20)
large_fills = [f for f in fills if float(f.get("size",0)) * float(f.get("price",0)) > 5000]
whale_direction = "YES" if sum(1 for f in large_fills if f.get("side","").upper() == "BUY") > len(large_fills)/2 else "NO"
# Rule: align with whale direction OR have strong contrarian evidence
```

## MARKET CATEGORIES AND EDGE SOURCES

### Weather Markets (best edge source)
- Edge: ECMWF forecast vs market-implied probability
- Tool: Open-Meteo API (free, 6hr updates)
- Entry: When forecast differs from market by >8%
- Exit: 48h before resolution (gamma risk explodes)

### Crypto/Price Markets
- Edge: Technical analysis + on-chain data
- Tools: CoinGecko API, Glassnode (if available)
- Caution: Highly correlated with BTC — check macro first
- Never trade during Fed announcements or major catalysts

### Political/Election Markets
- Edge: Polling aggregators vs market price
- Tools: FiveThirtyEight (via Playwright), Polymarket itself
- Caution: Fat tail risk — markets can go 0→100 instantly
- Max position: 2% of bankroll

### Sports Markets
- Edge: Injury news before market reprices
- Tools: Playwright → ESPN, Twitter/X injury reports
- Time sensitive: enter within 5min of injury report

### Tweet/Social Count Markets
- Edge: Real-time counter vs market projection
- Tools: XTracker at https://xtracker.polymarket.com
- Pattern: Market underprices low probability if count trajectory is clear

## WHEN TO WALK AWAY
- End date is None or "Unknown" → SKIP (resolution risk)
- Volume < $5,000 7d → SKIP (illiquid trap)
- Price is 95-99% or 1-5% → SKIP (no edge, all downside)
- Market title contains "OR" → SKIP (ambiguous resolution)
- Market already has >50 recent fills → SKIP (already being traded)

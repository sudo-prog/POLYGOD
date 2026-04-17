---
name: analyse-market
description: Deep analysis of Polymarket protocol. Use when users ask to analyze prediction markets, evaluate market liquidity, assess odds confidence, track market trends, or understand market sentiment on Polymarket.
---

# Analyse Market Skill

An expert agent for deep analysis of Polymarket prediction markets.

## Capabilities

- **Market Data Analysis**: Evaluate market prices, volumes, and liquidity
- **Odds Confidence Assessment**: Analyze implied probabilities and market confidence
- **Liquidity Analysis**: Measure market depth and trading activity
- **Trend Tracking**: Monitor market movements and sentiment shifts
- **Market Comparison**: Compare similar markets across different questions
- **Risk Assessment**: Evaluate market resolve probability and uncertainty

## Polymarket Data Sources

### API Endpoints

```python
# Get market data from Polymarket
import requests

def get_market_data(market_id: str) -> dict:
    """Fetch detailed market data."""
    url = f"https://clob.polymarket.com/markets/{market_id}"
    response = requests.get(url)
    return response.json()

def get_active_markets(category: str = None) -> list:
    """Fetch active markets, optionally filtered by category."""
    url = "https://clob.polymarket.com/markets"
    params = {"category": category} if category else {}
    return requests.get(url, params=params).json()
```

### Key Metrics

| Metric | Description |
|--------|-------------|
| Current Price | Binary outcome price (0-1 scale) |
| Volume | Total trading volume in USD |
| Liquidity | Available liquidity in USD |
| Spread | Bid-ask spread percentage |
| Market Cap | Price × Liquidity |
| Unique Traders | Number of unique addresses |

## Analysis Workflow

### Step 1: Fetch Market Data

1. Get market details (question, outcomes, prices)
2. Fetch historical price data
3. Collect trading volume history

### Step 2: Calculate Metrics

```python
def calculate_confidence(yes_price: float) -> dict:
    """Calculate market confidence metrics."""
    no_price = 1 - yes_price
    implied_prob = yes_price
    uncertainty = min(yes_price, no_price) * 2  # Binary spread

    return {
        "yes_probability": yes_price,
        "no_probability": no_price,
        "uncertainty": uncertainty,
        "confidence": 1 - uncertainty
    }
```

### Step 3: Liquidity Analysis

```python
def analyze_liquidity(market: dict) -> dict:
    """Analyze market liquidity depth."""
    return {
        "total_liquidity": market.get("liquidity", 0),
        "avg_spread": calculate_spread(market),
        "volume_24h": market.get("volume24hr", 0),
        "trade_count": market.get("tradeCount", 0)
    }
```

### Step 4: Trend Analysis

- Compare current price to historical averages
- Identify price movements and patterns
- Detect anomalies or unusual activity

## Market Categories

- Politics (elections, policies)
- Science (research outcomes)
- Technology (product releases)
- Sports (game outcomes)
- Economics (indicator predictions)
- Entertainment (award results)

## Output Format

Provide:
1. Market overview (question, categories, timestamps)
2. Current pricing with confidence metrics
3. Liquidity and volume analysis
4. Trend visualization
5. Risk assessment and recommendations

## Example Analysis

```
Market: "Will BTC exceed $100k by 2025?"
- Current Price: $0.35 (35% yes probability)
- Liquidity: $2.5M
- Volume 24h: $450K
- Confidence: 70%
- Risk Level: Medium

Analysis: Market shows moderate confidence with substantial
liquidity. Price suggests uncertainty about BTC reaching
$100k target.
```

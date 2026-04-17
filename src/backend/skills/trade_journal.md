# SKILL: TRADE_JOURNAL

Structured trade logging for post-mortem analysis and self-improvement.
Every trade (paper AND live) must be logged here. No exceptions.

## JOURNAL ENTRY FORMAT

```python
from datetime import datetime, timezone

def create_journal_entry(state: dict, execution_result: dict) -> dict:
    return {
        "run_id": state.get("run_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market_id": state.get("market_id"),
        "market_title": state.get("question", "")[:100],

        # Decision
        "verdict": state.get("verdict", "")[:200],
        "confidence_pct": state.get("confidence", 0),
        "kelly_fraction": state.get("kelly_fraction", 0),
        "risk_status": state.get("risk_status", "unknown"),

        # Execution
        "mode": state.get("mode", 0),
        "trade_type": "live" if state.get("mode", 0) == 3 else "paper",
        "side": execution_result.get("side", "unknown"),
        "size_usd": execution_result.get("size", 0),
        "status": execution_result.get("status", "unknown"),
        "order_id": execution_result.get("order_id"),

        # Market context
        "entry_price": state.get("market_data", {}).get("yes_percentage", 50),
        "liquidity": state.get("market_data", {}).get("liquidity", 0),
        "volume_7d": state.get("market_data", {}).get("volume", 0),

        # Agent outputs (abbreviated for readability)
        "statistics_summary": state.get("statistics", "")[:200],
        "debate_rounds": state.get("debate_round", 0),
        "whale_context": state.get("whale_context", "")[:100],

        # Simulation
        "monte_carlo": state.get("simulation", {}),

        # Outcome (filled in later by hindsight_replay)
        "resolution": None,
        "actual_pnl": None,
        "was_correct": None,
    }
```

## STORING A JOURNAL ENTRY

```python
async def log_trade(entry: dict):
    """Store trade journal entry to Mem0 AND MemPalace."""
    import json
    from src.backend.polygod_graph import mem0_add
    from src.backend.agents.mempalace_bridge import mempalace_bridge

    entry_json = json.dumps(entry, default=str)

    # Mem0: for pattern matching in hindsight_replay
    mem0_add(
        f"TRADE_JOURNAL: {entry_json}",
        user_id=f"trades_{entry['market_id']}"
    )

    # MemPalace: for operator review and cross-session search
    content = (
        f"TRADE: {entry['market_title']}\n"
        f"Verdict: {entry['verdict']}\n"
        f"Confidence: {entry['confidence_pct']}%\n"
        f"Side: {entry['side']} ${entry['size_usd']}\n"
        f"Risk: {entry['risk_status']}\n"
        f"Entry price: {entry['entry_price']}%\n"
        f"Timestamp: {entry['timestamp']}"
    )
    await mempalace_bridge.remember_decision(
        decision=f"TRADE {entry['side']} on {entry['market_title']}",
        rationale=entry['verdict'],
        component="trade_execution"
    )
```

## WEEKLY REVIEW QUERY

```python
async def weekly_trade_review() -> str:
    """Run before hindsight_replay() to get structured review."""
    from src.backend.polygod_graph import mem0_search

    # Find all recent trade entries
    trades = mem0_search("TRADE_JOURNAL", user_id="polygod")

    # Summarise with LLM
    from src.backend.services.llm_concierge import concierge
    response = await concierge.get_secure_completion(
        messages=[{
            "role": "user",
            "content": f"Analyse these {len(trades.split('|'))} trades. "
                       f"What patterns led to wins? What to avoid? "
                       f"Give 3 specific strategy improvements.\n\n{trades[:3000]}"
        }]
    )
    return response.choices[0].message.content if hasattr(response, 'choices') else str(response)
```

## WHEN TO REVIEW
- After every 10 paper trades: run weekly_trade_review()
- Every Sunday: full hindsight_replay() uses this data
- After any live trade: immediate single-trade review
- After any big loss (> 20% of position): mandatory post-mortem

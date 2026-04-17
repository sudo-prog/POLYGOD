# SKILL: ALERT_RULES

When POLYGOD should proactively message the operator WITHOUT being asked.
Send via Telegram to TELEGRAM_CHAT_ID.

## SEND ALERT FOR:

### Trading Signals (HIGH PRIORITY)
- debate verdict confidence > 85% → "🎯 High-confidence signal: {market} {verdict} {confidence}%"
- Whale detected > $50k in single fill → "🐋 MEGA WHALE: ${size} {side} on {market}"
- Kelly fraction > 0.3 (rare high edge) → "💎 EXCEPTIONAL EDGE: Kelly={kelly:.0f}% on {market}"
- BEAST MODE trade executed → "💰 LIVE TRADE: {side} ${size} on {market} | order_id={id}"

### System Health (MEDIUM PRIORITY)
- RAM > 85% for > 5 minutes → "⚠️ RAM HIGH: {pct}% — consider reducing variants"
- All LLM providers failing → "🚨 LLM OUTAGE: all providers down — AI disabled"
- Scheduler stopped unexpectedly → "🚨 SCHEDULER DEAD — market updates halted"
- DB disconnected → "🚨 DATABASE DOWN — all features degraded"

### Evolution Events (LOW PRIORITY)
- AutoResearch mutation kept (sharpe > 2.0) → "🧬 EVOLUTION: mutation kept | sharpe={sharpe:.2f}"
- Weekly hindsight replay complete → "📊 WEEKLY REPLAY: {n} memories processed"
- Memory pruning removed > 100 entries → "🧹 PRUNED: {n} low-value memories removed"

### Market Events (OPERATOR CHOICE)
- Market resolving in < 24h where POLYGOD has a position → resolution reminder
- Major price move (>10% in 1h) on a tracked market → "📈 PRICE ALERT: {market} moved {change}%"

## ALERT FORMAT
```python
async def send_alert(message: str, priority: str = "medium"):
    """Send proactive alert to operator."""
    from src.backend.config import settings
    chat_id = settings.TELEGRAM_CHAT_ID
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID not set — alert suppressed")
        return

    icons = {"high": "🚨", "medium": "⚠️", "low": "ℹ️"}
    full_msg = f"{icons.get(priority, 'ℹ️')} *POLYGOD ALERT*\n\n{message}"

    # Import the running app if available
    try:
        from src.backend.routes.telegram import app_telegram
        if app_telegram:
            await app_telegram.bot.send_message(
                chat_id=int(chat_id),
                text=full_msg,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Alert send failed: {e}")
```

## DO NOT ALERT FOR:
- Normal paper trades (too noisy)
- Individual API rate limits (handled automatically)
- News circuit breaker (self-heals)
- Mode 0 verdicts (observe only, no action needed)
- Any error that was auto-fixed successfully

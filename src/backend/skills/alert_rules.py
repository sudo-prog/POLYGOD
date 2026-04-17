"""
POLYGOD Alert Rules — Proactive notifications via Telegram.

This module implements the alert_rules.md skill for sending proactive
alerts to the operator when POLYGOD detects important events.
"""

import logging

logger = logging.getLogger(__name__)


async def send_alert(message: str, priority: str = "medium"):
    """Send proactive alert to operator."""
    try:
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
                    chat_id=int(chat_id), text=full_msg, parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Alert send failed: {e}")
    except Exception as e:
        logger.error(f"Alert system error: {e}")


async def alert_trading_signal(market: str, verdict: str, confidence: float):
    """Alert for high-confidence trading signals."""
    if confidence >= 85:
        await send_alert(
            f"🎯 High-confidence signal: {market} {verdict} {confidence:.0f}%",
            priority="high",
        )


async def alert_whale_trade(size: float, side: str, market: str):
    """Alert for large whale trades."""
    if size >= 50000:  # $50k+
        await send_alert(
            f"🐋 MEGA WHALE: ${size:,.0f} {side} on {market}", priority="high"
        )


async def alert_exceptional_edge(kelly: float, market: str):
    """Alert for rare high-edge opportunities."""
    if kelly >= 0.3:
        await send_alert(
            f"💎 EXCEPTIONAL EDGE: Kelly={kelly:.1%} on {market}", priority="high"
        )


async def alert_live_trade(side: str, size: float, market: str, order_id: str):
    """Alert for live trades executed."""
    await send_alert(
        f"💰 LIVE TRADE: {side} ${size:,.0f} on {market} | order_id={order_id}",
        priority="high",
    )


async def alert_system_health(metric: str, value: float, threshold: float):
    """Alert for system health issues."""
    if metric == "ram_pct" and value >= 85:
        await send_alert(
            f"⚠️ RAM HIGH: {value:.0f}% — consider reducing variants", priority="medium"
        )


async def alert_llm_outage():
    """Alert when all LLM providers fail."""
    await send_alert("🚨 LLM OUTAGE: all providers down — AI disabled", priority="high")


async def alert_scheduler_dead():
    """Alert when the scheduler stops unexpectedly."""
    await send_alert("🚨 SCHEDULER DEAD — market updates halted", priority="high")


async def alert_database_down():
    """Alert when database connection is lost."""
    await send_alert("🚨 DATABASE DOWN — all features degraded", priority="high")


async def alert_evolution_event(message: str):
    """Alert for evolution events (low priority)."""
    await send_alert(message, priority="low")


async def alert_market_event(message: str):
    """Alert for market events (operator choice)."""
    await send_alert(message, priority="medium")

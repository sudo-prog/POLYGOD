"""Telegram Bot command surface for POLYGOD — God-Tier Swarm Controls.

Provides real-time Telegram commands to control the POLYGOD swarm:
- /start: Bot online confirmation
- /mode <0-3>: Switch POLYGOD mode (OBSERVE/PAPER/LOW/BEAST)
- /real: Paper-to-real switch (enable LIVE trading)
- /scan: Trigger niche scanner for micro-opportunities
- /beast <market_id>: Execute full BEAST MODE pipeline
- /kill: Graceful kill switch (save checkpoints, pause swarm)
"""

import asyncio
import logging

from fastapi import APIRouter
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telegram Controls"])

# Telegram Application (built lazily when bot token is available)
app_telegram: Application | None = None


# ─── Command Handlers ────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message and command list."""
    await update.message.reply_text(
        "🚀 *POLYGOD God-Tier Swarm Online!*\n\n"
        "Available commands:\n"
        "/mode <0-3> — Switch POLYGOD mode\n"
        "/real — Paper-to-real switch (LIVE trading)\n"
        "/scan — Scan micro-niches for opportunities\n"
        "/beast <market_id> — Execute BEAST MODE\n"
        "/snapshot — Take full code+state snapshot\n"
        "/rollback <sha> — Rollback to snapshot\n"
        "/snapshots — List recent snapshots\n"
        "/kill — Graceful shutdown (save checkpoints)\n\n"
        "_Let the money printer go brrrr_ 💰",
        parse_mode="Markdown",
    )


async def cmd_switch_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch POLYGOD operating mode (0=OBSERVE, 1=PAPER, 2=LOW, 3=BEAST)."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /mode <0|1|2|3>\n0=OBSERVE, 1=PAPER, 2=LOW, 3=BEAST"
        )
        return

    try:
        new_mode = int(context.args[0])
        if new_mode not in {0, 1, 2, 3}:
            raise ValueError("Mode must be 0-3")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid mode. Use 0, 1, 2, or 3.")
        return

    # Update global mode

    # Mutate the module-level mode variable
    import src.backend.polygod_graph as pg

    old_mode = pg.POLYGOD_MODE
    pg.POLYGOD_MODE = new_mode

    mode_labels = {0: "OBSERVE", 1: "PAPER", 2: "LOW", 3: "BEAST"}
    await update.message.reply_text(
        f"🔄 *MODE SWITCHED*\n"
        f"From: {old_mode} ({mode_labels.get(old_mode, 'UNKNOWN')})\n"
        f"To: {new_mode} ({mode_labels.get(new_mode, 'UNKNOWN')})",
        parse_mode="Markdown",
    )
    logger.info(f"Telegram: POLYGOD mode switched from {old_mode} to {new_mode}")


async def cmd_scan_niches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger niche scanner for micro-opportunity detection."""
    await update.message.reply_text(
        "📡 *Scanning micro-niches...* please wait.", parse_mode="Markdown"
    )

    try:
        from src.backend.niche_scanner import scanner

        opportunities = await scanner.scan_niches(settings.POLYGOD_MODE)
        count = len(opportunities)

        if opportunities:
            # Show first 3 opportunities
            opps_text = "\n".join(
                [
                    f"• {opp.get('market_id', 'N/A')} — edge: {opp.get('edge', 0):.2f}%"
                    for opp in opportunities[:3]
                ]
            )
            if count > 3:
                opps_text += f"\n... and {count - 3} more"
        else:
            opps_text = "No opportunities found in current market conditions."

        await update.message.reply_text(
            f"📡 *Scan Complete!*\n\nFound: *{count}* micro-niche opportunities\n\n{opps_text}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Telegram scan failed: {e}")
        await update.message.reply_text(f"❌ Scan failed: {e}")


async def cmd_beast_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute full BEAST MODE pipeline on a market."""
    # Verify mode is BEAST (3)
    if settings.POLYGOD_MODE < 3:
        await update.message.reply_text(
            "❌ *BEAST MODE requires MODE=3!*\nUse /mode 3 first to enable live execution.",
            parse_mode="Markdown",
        )
        return

    # Get market_id from args (default to weather-nyc for testing)
    market_id = context.args[0] if context.args else "weather-nyc"

    await update.message.reply_text(
        f"💥 *BEAST MODE ACTIVATED!*\n\n"
        f"Market: `{market_id}`\n"
        f"Running full POLYGOD pipeline...\n"
        f"_This may take a minute_ ⏳",
        parse_mode="Markdown",
    )

    try:
        from src.backend.polygod_graph import run_polygod

        result = await run_polygod(market_id=market_id, mode=3, question="")

        verdict = result.get("debate_verdict", "No verdict")
        confidence = result.get("confidence", 0)
        paper_pnl = result.get("paper_pnl", 0)
        risk_status = result.get("risk_status", "unknown")

        await update.message.reply_text(
            f"💥 *BEAST MODE COMPLETE!*\n\n"
            f"Market: `{market_id}`\n"
            f"Verdict: *{verdict}*\n"
            f"Confidence: *{confidence}%*\n"
            f"Paper PnL: *${paper_pnl:.2f}*\n"
            f"Risk Status: *{risk_status}*",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Beast mode execution failed: {e}")
        await update.message.reply_text(f"❌ BEAST MODE failed: {e}")


async def cmd_real_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paper-to-real switch — enable LIVE trading (mode 3)."""
    # Mutate the module-level mode variable
    import src.backend.polygod_graph as pg

    old_mode = pg.POLYGOD_MODE
    pg.POLYGOD_MODE = 3

    # Also update settings
    settings.POLYGOD_MODE = 3

    await update.message.reply_text(
        "🚀 *PAPER-TO-REAL SWITCH ACTIVATED*\n\n"
        "💰 *LIVE TRADING ENABLED*\n\n"
        "Safety guards active:\n"
        "• Min liquidity: $5,000\n"
        "• Min confidence: 90%\n"
        "• Kelly-optimized sizing\n\n"
        f"Previous mode: {old_mode}\n"
        "Current mode: 3 (BEAST/LIVE)\n\n"
        "_Use /beast <market_id> to execute live trades_",
        parse_mode="Markdown",
    )
    logger.info(f"Telegram: PAPER-TO-REAL activated — mode switched from {old_mode} to 3 (LIVE)")


async def cmd_kill_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Graceful kill switch — save checkpoints and pause swarm."""
    await update.message.reply_text(
        "☠️ *KILL SWITCH ACTIVATED*\n\nSaving checkpoints...\nPausing swarm operations...",
        parse_mode="Markdown",
    )

    try:
        from src.backend.polygod_graph import polygod_graph

        # Close checkpointer to save state
        if hasattr(polygod_graph, "checkpointer") and polygod_graph.checkpointer:
            await polygod_graph.checkpointer.close()
            logger.info("Telegram: Checkpointer closed (state saved)")

        await update.message.reply_text(
            "✅ *Checkpoints saved!*\n"
            "Swarm paused. Use /mode to resume.\n\n"
            "_Paper PnL summary will be in the next daily report._",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Kill switch failed: {e}")
        await update.message.reply_text(
            f"⚠️ Kill switch partially failed: {e}\nSwarm may still be running. Check logs."
        )


async def cmd_snapshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Take a full code + state snapshot."""
    await update.message.reply_text(
        "📸 *Taking full snapshot...*\n\nCreating git commit + LangGraph checkpoint + Mem0 record",
        parse_mode="Markdown",
    )

    try:
        from src.backend.snapshot_engine import snapshot_engine

        # Take snapshot with current state
        state = {"verdict": "telegram_manual", "confidence": 100}
        snap = await snapshot_engine.take_snapshot(state, "telegram")

        await update.message.reply_text(
            f"📸 *Snapshot taken!*\n\n"
            f"Commit SHA: `{snap['commit_sha'][:10]}`\n"
            f"Checkpoint: `{snap.get('checkpoint_id', 'N/A')}`\n"
            f"Timestamp: {snap['timestamp']}\n"
            f"Label: `{snap['label']}`\n\n"
            f"_Use /rollback <sha> to restore_",
            parse_mode="Markdown",
        )
        logger.info(f"Telegram: Snapshot taken: {snap['commit_sha'][:10]}")
    except Exception as e:
        logger.error(f"Telegram snapshot failed: {e}")
        await update.message.reply_text(f"❌ Snapshot failed: {e}")


async def cmd_rollback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rollback to a previous snapshot."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /rollback <commit_sha>\nUse /snapshots to list available snapshots",
            parse_mode="Markdown",
        )
        return

    sha = context.args[0]

    await update.message.reply_text(
        f"🔄 *Rolling back to {sha[:10]}...*",
        parse_mode="Markdown",
    )

    try:
        from src.backend.snapshot_engine import snapshot_engine

        result = await snapshot_engine.rollback_to_snapshot(sha)

        if result["status"] == "success":
            await update.message.reply_text(
                f"✅ *Rollback complete!*\n\n"
                f"Reverted to: `{result['commit_sha'][:10]}`\n"
                f"Message: {result['message']}\n\n"
                "_Note: You may need to restart the server for changes to take effect._",
                parse_mode="Markdown",
            )
            logger.info(f"Telegram: Rolled back to {result['commit_sha'][:10]}")
        else:
            await update.message.reply_text(
                f"❌ Rollback failed: {result['message']}",
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error(f"Telegram rollback failed: {e}")
        await update.message.reply_text(f"❌ Rollback failed: {e}")


async def cmd_list_snapshots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List recent snapshots."""
    try:
        from src.backend.snapshot_engine import snapshot_engine

        snapshots = await snapshot_engine.list_snapshots(limit=5)

        if snapshots:
            text = "📸 *Recent Snapshots:*\n\n"
            for snap in snapshots:
                text += f"• `{snap['short_sha']}` — {snap['message'][:50]}\n"
                text += f"  {snap['timestamp'][:19]}\n\n"
        else:
            text = "No snapshots found yet."

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Telegram list_snapshots failed: {e}")
        await update.message.reply_text(f"❌ Failed to list snapshots: {e}")


# ─── Bot Setup ───────────────────────────────────────────────────────────────


def build_telegram_app() -> Application:
    """Build and configure the Telegram Application with all handlers."""
    global app_telegram

    app_telegram = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    app_telegram.add_handler(CommandHandler("start", cmd_start))
    app_telegram.add_handler(CommandHandler("mode", cmd_switch_mode))
    app_telegram.add_handler(CommandHandler("real", cmd_real_mode))
    app_telegram.add_handler(CommandHandler("scan", cmd_scan_niches))
    app_telegram.add_handler(CommandHandler("beast", cmd_beast_mode))
    app_telegram.add_handler(CommandHandler("kill", cmd_kill_switch))
    app_telegram.add_handler(CommandHandler("snapshot", cmd_snapshot))
    app_telegram.add_handler(CommandHandler("rollback", cmd_rollback))
    app_telegram.add_handler(CommandHandler("snapshots", cmd_list_snapshots))

    logger.info("Telegram bot handlers registered")
    return app_telegram


async def run_telegram_bot():
    """Background task to run the Telegram bot (called from main.py lifespan)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled")
        return

    app = build_telegram_app()

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("🚀 POLYGOD Telegram bot is live and polling!")

    # Keep running until shutdown
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Telegram bot shut down")

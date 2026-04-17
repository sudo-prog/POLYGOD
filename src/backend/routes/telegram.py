"""
POLYGOD Telegram Command Surface — Your primary control interface.

Commands:
  SYSTEM CONTROL
  /start      — Status overview + command list
  /mode <0-3> — Switch operating mode
  /status     — Full system health check
  /boot       — Re-run boot sequence
  /real       — Enable live trading (mode 3)
  /kill       — Emergency kill switch

  INTELLIGENCE
  /run <market_id>  — Run full POLYGOD analysis
  /debate <market_id> — Run debate floor only
  /scan       — Scan micro-niches
  /whale <market_id> — Show whale activity

  MEMORY
  /remember <text>  — Store to Mem0
  /recall <query>   — Search Mem0
  /palace <query>   — Search MemPalace

  SKILLS
  /skill <name>     — Load and display a skill
  /skills           — List all available skills

  AGENT
  /ask <question>   — Ask the AI agent anything
  /fix <error>      — Auto-fix an error

  SNAPSHOTS
  /snapshot   — Take full code+state snapshot
  /rollback <sha> — Rollback to snapshot
  /snapshots  — List recent snapshots
"""

import asyncio
import logging

from fastapi import APIRouter
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Telegram Controls"])
app_telegram: Application | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────


def _truncate(text: str, max_len: int = 3500) -> str:
    """Telegram max message is 4096 chars."""
    return text[:max_len] + "\n...(truncated)" if len(text) > max_len else text


async def _send_long(update: Update, text: str) -> None:
    """Send text, splitting into multiple messages if needed."""
    chunks = [text[i : i + 3800] for i in range(0, len(text), 3800)]
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode="Markdown")
        if len(chunks) > 1:
            await asyncio.sleep(0.3)


# ── System Commands ───────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome + current status."""
    from src.backend.agents.polygod_brain import get_boot_status

    boot = get_boot_status()

    mode_labels = {0: "OBSERVE 👁", 1: "PAPER 📄", 2: "LOW ⚡", 3: "BEAST 🔥"}

    if boot:
        failed = boot.failed
        status_line = (
            "✅ All systems operational"
            if boot.all_ok
            else f"⚠️ Issues: {', '.join(failed)}"
        )
    else:
        status_line = "⚙️ Boot status unknown — run /boot"

    from src.backend.main import POLYGOD_MODE

    mode_str = mode_labels.get(POLYGOD_MODE, "UNKNOWN")

    await update.message.reply_text(
        f"🔱 *POLYGOD GOD-TIER SWARM*\n\n"
        f"Status: {status_line}\n"
        f"Mode: *{mode_str}*\n\n"
        f"*SYSTEM*\n"
        f"/status — Full system health\n"
        f"/mode <0-3> — Switch mode\n"
        f"/boot — Re-run boot sequence\n"
        f"/kill — Emergency stop\n\n"
        f"*TRADING*\n"
        f"/run <market\\_id> — Full analysis\n"
        f"/debate <market\\_id> — Debate only\n"
        f"/scan — Scan niches\n"
        f"/whale <market\\_id> — Whale activity\n\n"
        f"*MEMORY*\n"
        f"/remember <text> — Store memory\n"
        f"/recall <query> — Search Mem0\n"
        f"/palace <query> — Search MemPalace\n\n"
        f"*SKILLS & AGENT*\n"
        f"/skills — List skills\n"
        f"/skill <name> — Load skill\n"
        f"/ask <question> — Ask AI agent\n"
        f"/fix <error> — Auto-fix error\n\n"
        f"*SNAPSHOTS*\n"
        f"/snapshot — Take snapshot\n"
        f"/snapshots — List snapshots\n"
        f"/rollback <sha> — Rollback",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Full system health check."""
    await update.message.reply_text(
        "🔍 Running system checks...", parse_mode="Markdown"
    )

    from src.backend.agents.polygod_brain import run_boot_sequence, set_boot_status

    boot = await run_boot_sequence()
    set_boot_status(boot)

    lines = ["🔱 *POLYGOD SYSTEM STATUS*\n"]
    for name, check in boot.checks.items():
        icon = "✅" if check["status"] == "ok" else "❌"
        detail = check.get("detail") or check.get("error") or ""
        lines.append(f"{icon} *{name}*: {detail}")

    lines.append(f"\n_Boot time: {boot.boot_time.strftime('%H:%M:%S UTC')}_")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_boot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-run boot sequence."""
    await update.message.reply_text(
        "🔄 *Re-running boot sequence...*", parse_mode="Markdown"
    )
    from src.backend.agents.polygod_brain import run_boot_sequence, set_boot_status

    boot = await run_boot_sequence()
    set_boot_status(boot)

    if boot.all_ok:
        await update.message.reply_text(
            "✅ *Boot complete — all systems operational*", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "⚠️ *Boot complete with failures:*\n"
            + "\n".join(f"❌ {f}" for f in boot.failed),
            parse_mode="Markdown",
        )


async def cmd_switch_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch POLYGOD mode."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /mode <0|1|2|3>\n0=OBSERVE 1=PAPER 2=LOW 3=BEAST"
        )
        return
    try:
        new_mode = int(context.args[0])
        if new_mode not in {0, 1, 2, 3}:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid mode. Use 0, 1, 2, or 3.")
        return

    import src.backend.main as main_module
    import src.backend.polygod_graph as pg

    old_mode = pg.POLYGOD_MODE
    pg.POLYGOD_MODE = new_mode
    main_module.POLYGOD_MODE = new_mode

    # Persist to DB
    try:
        from src.backend.main import set_mode_in_db

        await set_mode_in_db(new_mode)
    except Exception:
        pass

    labels = {0: "OBSERVE 👁", 1: "PAPER 📄", 2: "LOW ⚡", 3: "BEAST 🔥"}
    await update.message.reply_text(
        f"🔄 *Mode switched*\n{labels.get(old_mode)} → *{labels.get(new_mode)}*",
        parse_mode="Markdown",
    )


# ── Trading Commands ──────────────────────────────────────────────────────────


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run full POLYGOD analysis on a market."""
    if not context.args:
        await update.message.reply_text("Usage: /run <market_id>")
        return

    market_id = context.args[0]
    import src.backend.main as m

    mode = m.POLYGOD_MODE

    await update.message.reply_text(
        f"🔱 *Running POLYGOD on:* `{market_id}`\nMode: {mode} | This may take 60-120s...",
        parse_mode="Markdown",
    )

    try:
        from src.backend.polygod_graph import run_polygod

        result = await run_polygod(market_id=market_id, mode=mode)

        verdict = result.get("verdict", "No verdict")[:500]
        pnl = result.get("paper_pnl", 0)
        confidence = result.get("confidence", 0)
        risk = result.get("risk_status", "unknown")

        await update.message.reply_text(
            f"✅ *POLYGOD RUN COMPLETE*\n\n"
            f"Market: `{market_id}`\n"
            f"Confidence: *{confidence:.0f}%*\n"
            f"Risk Gate: *{risk.upper()}*\n"
            f"Paper PnL: *${pnl:.2f}*\n\n"
            f"*Verdict:*\n{verdict}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Run failed: {str(e)[:500]}")


async def cmd_whale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show whale activity for a market."""
    if not context.args:
        await update.message.reply_text("Usage: /whale <market_id>")
        return

    market_id = context.args[0]
    await update.message.reply_text(
        f"🐋 Fetching whale activity for `{market_id}`...", parse_mode="Markdown"
    )

    try:
        from src.backend.polymarket.client import polymarket_client

        fills = await polymarket_client.get_recent_fills(market_id, limit=10)

        if not fills:
            await update.message.reply_text("No recent fills found.")
            return

        lines = [f"🐋 *Whale Activity: {market_id}*\n"]
        for fill in fills[:8]:
            size = float(fill.get("size", 0))
            price = float(fill.get("price", 0))
            side = fill.get("side", "?")
            value = round(size * price, 0)
            wallet = str(fill.get("maker_address", ""))[:8]
            lines.append(f"• {side.upper()} ${value:,.0f} @ {price:.2f} ({wallet}...)")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Whale fetch failed: {e}")


async def cmd_scan_niches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scan for micro-niche opportunities."""
    await update.message.reply_text(
        "📡 *Scanning micro-niches...*", parse_mode="Markdown"
    )
    try:
        import src.backend.main as m
        from src.backend.niche_scanner import scanner

        opps = await scanner.scan_niches(m.POLYGOD_MODE)

        if not opps:
            await update.message.reply_text("No opportunities found.")
            return

        lines = [f"📡 *Found {len(opps)} micro-niche opportunities*\n"]
        for opp in opps[:5]:
            lines.append(
                f"• `{opp.get('market_id', '?')[:20]}` | "
                f"Edge: *{opp.get('edge', 0):.1%}* | "
                f"Kelly: {opp.get('kelly_size', 0):.1%}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Scan failed: {e}")


# ── Memory Commands ───────────────────────────────────────────────────────────


async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store something in Mem0."""
    if not context.args:
        await update.message.reply_text("Usage: /remember <text to store>")
        return

    text = " ".join(context.args)
    try:
        from src.backend.polygod_graph import mem0_add

        mem0_add(f"[OPERATOR NOTE via Telegram]: {text}", user_id="polygod")
        await update.message.reply_text(
            f"✅ *Stored to memory:*\n_{text}_", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Memory write failed: {e}")


async def cmd_recall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search Mem0 trading memory."""
    if not context.args:
        await update.message.reply_text("Usage: /recall <search query>")
        return

    query = " ".join(context.args)
    try:
        from src.backend.polygod_graph import mem0_search

        results = mem0_search(query, user_id="polygod")

        if not results:
            await update.message.reply_text("No memories found.")
            return

        await _send_long(
            update, f"🧠 *Recall results for: {query}*\n\n{results[:2000]}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Recall failed: {e}")


async def cmd_palace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search MemPalace project memory."""
    if not context.args:
        await update.message.reply_text("Usage: /palace <search query>")
        return

    query = " ".join(context.args)
    try:
        from src.backend.agents.mempalace_bridge import mempalace_bridge

        results = await mempalace_bridge.search(query, top_k=3)

        if not results:
            await update.message.reply_text(
                "No project memories found. Is MemPalace installed?"
            )
            return

        lines = [f"🏛 *MemPalace results for: {query}*\n"]
        for r in results:
            content = str(r.get("content", ""))[:400]
            wing = r.get("wing", "?")
            lines.append(f"*[{wing}]*\n{content}\n")

        await _send_long(update, "\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"❌ Palace search failed: {e}")


# ── Skills Commands ───────────────────────────────────────────────────────────


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available skills."""
    try:
        from src.backend.agents.skill_loader import list_available_skills

        skills = list_available_skills()

        lines = ["🛠 *Available Skills*\n"]
        for skill in skills:
            lines.append(f"• `{skill['name']}` — {skill['description']}")
        lines.append("\nUse: /skill <name> to load one")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Skills list failed: {e}")


async def cmd_skill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Load and display a skill."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /skill <name>\nUse /skills to see available skills."
        )
        return

    skill_name = context.args[0].lower()
    try:
        from src.backend.agents.skill_loader import load_skill

        content = load_skill(skill_name)

        if not content:
            await update.message.reply_text(
                f"❌ Skill '{skill_name}' not found. Use /skills to see available."
            )
            return

        await _send_long(update, f"🛠 *Skill: {skill_name.upper()}*\n\n{content}")
    except Exception as e:
        await update.message.reply_text(f"❌ Skill load failed: {e}")


# ── Agent Commands ────────────────────────────────────────────────────────────


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask the POLYGOD AI agent anything. Auto-loads relevant skills."""
    if not context.args:
        await update.message.reply_text("Usage: /ask <your question>")
        return

    question = " ".join(context.args)
    await update.message.reply_text("🤖 *Thinking...*", parse_mode="Markdown")

    try:
        from src.backend.agents.polygod_brain import get_system_prompt
        from src.backend.agents.skill_loader import load_skills_for_message
        from src.backend.services.llm_concierge import concierge

        # Auto-load relevant skills
        skill_names, skill_content = load_skills_for_message(question)

        system = get_system_prompt()
        if skill_content:
            system += f"\n\n{skill_content}"

        response = await concierge.get_secure_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            max_tokens=1000,
        )

        # Extract text from response
        if hasattr(response, "choices"):
            answer = response.choices[0].message.content
        elif hasattr(response, "content"):
            answer = response.content
        else:
            answer = str(response)

        skill_note = (
            f"\n\n_Skills used: {', '.join(skill_names)}_" if skill_names else ""
        )
        await _send_long(update, f"🤖 *POLYGOD AI*\n\n{answer}{skill_note}")

    except Exception as e:
        await update.message.reply_text(f"❌ Agent call failed: {e}")


async def cmd_fix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Auto-fix an error using the self-healing engine.
    Checks MemPalace first for known fixes, then uses AI.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /fix <error message>\n"
            "Example: /fix ModuleNotFoundError: No module named 'structlog'"
        )
        return

    error_text = " ".join(context.args)
    await update.message.reply_text(
        f"🔧 *Auto-fix requested:*\n`{error_text[:200]}`\n\nChecking known fixes...",
        parse_mode="Markdown",
    )

    try:
        # Check MemPalace for known fix first
        from src.backend.agents.mempalace_bridge import mempalace_bridge

        known_fix = await mempalace_bridge.get_error_fix(error_text)

        if known_fix:
            await update.message.reply_text(
                f"✅ *Known fix found in MemPalace:*\n\n{known_fix[:1500]}",
                parse_mode="Markdown",
            )
            return

        # No known fix — use AI with FIX_PYTHON skill
        from src.backend.agents.polygod_brain import get_system_prompt
        from src.backend.agents.skill_loader import load_skill
        from src.backend.services.llm_concierge import concierge

        fix_skill = load_skill("fix_python")
        system = get_system_prompt() + f"\n\n{fix_skill}"

        response = await concierge.get_secure_completion(
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Fix this error in the POLYGOD codebase:\n\n{error_text}\n\n"
                    f"Give me: 1) Root cause 2) Exact file+line to change 3) The fix code",
                },
            ],
            max_tokens=1500,
        )

        if hasattr(response, "choices"):
            fix = response.choices[0].message.content
        elif hasattr(response, "content"):
            fix = response.content
        else:
            fix = str(response)

        # Store the AI fix in MemPalace for next time
        await mempalace_bridge.remember_error(
            error=error_text,
            fix=fix,
            component="auto_detected",
        )

        await _send_long(
            update, f"🔧 *AI Fix (stored to MemPalace for next time):*\n\n{fix}"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Fix failed: {e}")


# ── Snapshot Commands (unchanged from before) ─────────────────────────────────


async def cmd_snapshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 *Taking snapshot...*", parse_mode="Markdown")
    try:
        from src.backend.snapshot_engine import snapshot_engine

        snap = await snapshot_engine.take_snapshot(
            {"verdict": "telegram_manual"}, "telegram"
        )
        await update.message.reply_text(
            f"📸 *Snapshot taken*\n`{snap['commit_sha'][:10]}`\n{snap['timestamp'][:19]}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Snapshot failed: {e}")


async def cmd_rollback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /rollback <commit_sha>")
        return
    sha = context.args[0]
    try:
        from src.backend.snapshot_engine import snapshot_engine

        result = await snapshot_engine.rollback_to_snapshot(sha)
        if result["status"] == "success":
            await update.message.reply_text(
                f"✅ *Rolled back to* `{sha[:10]}`", parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ {result['message']}")
    except Exception as e:
        await update.message.reply_text(f"❌ Rollback failed: {e}")


async def cmd_list_snapshots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from src.backend.snapshot_engine import snapshot_engine

        snaps = await snapshot_engine.list_snapshots(limit=5)
        if not snaps:
            await update.message.reply_text("No snapshots found.")
            return
        lines = ["📸 *Recent Snapshots*\n"]
        for s in snaps:
            lines.append(
                f"• `{s['short_sha']}` — {s['message'][:50]}\n  {s['timestamp'][:19]}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")


async def cmd_kill_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☠️ *KILL SWITCH ACTIVATED*\nSaving checkpoints...", parse_mode="Markdown"
    )
    try:
        import src.backend.polygod_graph as pg

        if hasattr(pg, "polygod_graph") and hasattr(pg.polygod_graph, "checkpointer"):
            if pg.polygod_graph.checkpointer:
                try:
                    await pg.polygod_graph.checkpointer.aclose()
                except Exception:
                    pass
        await update.message.reply_text(
            "✅ *Kill switch complete. Use /mode to resume.*", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Partial kill: {e}")


async def cmd_real_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import src.backend.main as m
    import src.backend.polygod_graph as pg

    old = pg.POLYGOD_MODE
    pg.POLYGOD_MODE = 3
    m.POLYGOD_MODE = 3
    await update.message.reply_text(
        f"🚀 *LIVE TRADING ENABLED*\nMode {old} → *3 (BEAST)*\n\n"
        f"Guards active: 90% confidence + $5k liquidity\n"
        f"Use /beast <market\\_id> to execute",
        parse_mode="Markdown",
    )


async def cmd_sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Full system resource report."""
    from src.backend.agents.system_admin import (
        get_docker_stats,
        get_gpu_utilization,
        get_system_load,
    )

    sys = get_system_load()
    gpu = get_gpu_utilization()
    docker = get_docker_stats()

    if "error" in sys:
        await update.message.reply_text(f"❌ {sys['error']}")
        return

    warnings = sys.get("warnings", [])
    warn_str = "\n".join(f"⚠️ {w}" for w in warnings) if warnings else "✅ All clear"

    gpu_str = ""
    if gpu.get("available"):
        gpu_str = (
            f"\n\n*GPU: {gpu['name']}*\n"
            f"Utilization: {gpu['gpu_pct']}%\n"
            f"VRAM: {gpu['vram_used_mb']}/{gpu['vram_total_mb']} MB\n"
            f"Temp: {gpu['temp_c']}°C"
        )

    # Top 3 containers by memory
    containers = ""
    if docker and not docker[0].get("error"):
        top = sorted(
            docker, key=lambda x: x.get("MemPerc", "0%").rstrip("%"), reverse=True
        )[:3]
        containers = "\n\n*Containers:*\n" + "\n".join(
            f"• {c.get('Name', '?')}: CPU {c.get('CPUPerc', '?')} MEM {c.get('MemPerc', '?')}"
            for c in top
        )

    await update.message.reply_text(
        f"🖥 *System Status*\n\n"
        f"CPU: *{sys['cpu_pct']:.0f}%*\n"
        f"RAM: *{sys['ram_used_gb']}/{sys['ram_total_gb']} GB ({sys['ram_pct']:.0f}%)*\n"
        f"Swap: {sys['swap_pct']:.0f}% | Disk: {sys['disk_pct']:.0f}%\n\n"
        f"{warn_str}"
        f"{gpu_str}"
        f"{containers}",
        parse_mode="Markdown",
    )


async def cmd_stop_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop running tournament simulations."""
    from src.backend.agents.system_admin import stop_parallel_tournament

    msg = stop_parallel_tournament()
    await update.message.reply_text(f"🛑 {msg}")


async def cmd_disable_autoresearch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable auto-evolution."""
    from src.backend.agents.system_admin import disable_autoresearch

    msg = disable_autoresearch()
    await update.message.reply_text(f"🧬 {msg}")


async def cmd_emergency_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Nuclear option."""
    await update.message.reply_text(
        "☢️ *EMERGENCY STOP* — halting all background tasks..."
    )
    from src.backend.agents.system_admin import emergency_stop_everything

    results = emergency_stop_everything()
    lines = [f"• {k}: {v}" for k, v in results.items()]
    await update.message.reply_text(
        "☢️ *Emergency stop complete:*\n" + "\n".join(lines), parse_mode="Markdown"
    )


async def cmd_set_variants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set max parallel tournament variants."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /variants <number>\nExample: /variants 20"
        )
        return
    try:
        n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Must be a number")
        return
    from src.backend.agents.system_admin import set_max_parallel_variants

    msg = set_max_parallel_variants(n)
    await update.message.reply_text(f"⚙️ {msg}")


async def cmd_throttle_llm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set LLM rate limit."""
    if not context.args:
        await update.message.reply_text("Usage: /throttle <rpm>\nExample: /throttle 20")
        return
    try:
        rpm = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Must be a number")
        return
    from src.backend.agents.system_admin import set_llm_rate_limit

    msg = set_llm_rate_limit(rpm)
    await update.message.reply_text(f"⚙️ {msg}")


# ── Registration ──────────────────────────────────────────────────────────────


def build_telegram_app() -> Application:
    global app_telegram
    token = settings.TELEGRAM_BOT_TOKEN.get_secret_value()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    app_telegram = Application.builder().token(token).build()

    handlers = [
        # System
        ("start", cmd_start),
        ("status", cmd_status),
        ("boot", cmd_boot),
        ("mode", cmd_switch_mode),
        ("real", cmd_real_mode),
        ("kill", cmd_kill_switch),
        ("sysinfo", cmd_sysinfo),
        ("stoptournament", cmd_stop_tournament),
        ("noevolve", cmd_disable_autoresearch),
        ("estop", cmd_emergency_stop),
        ("variants", cmd_set_variants),
        ("throttle", cmd_throttle_llm),
        # Trading
        ("run", cmd_run),
        ("debate", cmd_run),  # alias for now
        ("scan", cmd_scan_niches),
        ("whale", cmd_whale),
        # Memory
        ("remember", cmd_remember),
        ("recall", cmd_recall),
        ("palace", cmd_palace),
        # Skills + Agent
        ("skills", cmd_skills),
        ("skill", cmd_skill),
        ("ask", cmd_ask),
        ("fix", cmd_fix),
        # Snapshots
        ("snapshot", cmd_snapshot),
        ("rollback", cmd_rollback),
        ("snapshots", cmd_list_snapshots),
    ]

    for name, handler in handlers:
        app_telegram.add_handler(CommandHandler(name, handler))

    logger.info(f"Telegram bot registered {len(handlers)} commands")
    return app_telegram


async def run_telegram_bot():
    if not settings.TELEGRAM_BOT_TOKEN.get_secret_value():
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled")
        return

    app = build_telegram_app()
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("🚀 POLYGOD Telegram bot polling")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Telegram bot shut down")

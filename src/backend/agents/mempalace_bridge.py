"""
MemPalace bridge for POLYGOD.

Connects MemPalace's structured project memory to the POLYGOD agent system.

Wings:
  wing_polygod   → system architecture, bugs, decisions
  wing_markets   → market-specific analysis and outcomes
  wing_operator  → operator preferences and instructions
  wing_errors    → error patterns and fixes (most valuable for self-healing)
"""

import logging
import subprocess
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# MemPalace is optional — graceful fallback if not installed
try:
    from mempalace.knowledge_graph import KnowledgeGraph
    from mempalace.searcher import search_memories

    _HAS_MEMPALACE = True
    logger.info("MemPalace available — project memory enabled")
except ImportError:
    _HAS_MEMPALACE = False
    logger.info(
        "MemPalace not installed — using Mem0 only. Install: pip install mempalace"
    )


class MemPalaceBridge:
    """
    Bridge between POLYGOD and MemPalace.

    Provides structured project memory separate from trading memory (Mem0).
    MemPalace remembers WHY decisions were made.
    Mem0 remembers HOW trades performed.
    """

    def __init__(self, palace_path: str = "~/.mempalace/palace"):
        self.palace_path = palace_path
        self.available = _HAS_MEMPALACE
        self._kg: Any = None

    def _get_kg(self):
        if not self.available:
            return None
        if self._kg is None:
            try:
                self._kg = KnowledgeGraph(palace_path=self.palace_path)
            except Exception as e:
                logger.warning(f"MemPalace KG init failed: {e}")
        return self._kg

    async def search(
        self,
        query: str,
        wing: str | None = None,
        room: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Search MemPalace for relevant project knowledge."""
        if not self.available:
            return []
        try:
            results = search_memories(
                query,
                palace_path=self.palace_path,
                wing=wing,
                room=room,
                top_k=top_k,
            )
            return list(results) if results else []
        except Exception as e:
            logger.warning(f"MemPalace search failed: {e}")
            return []

    async def remember_error(self, error: str, fix: str, component: str) -> bool:
        """
        Store an error + fix in MemPalace for future self-healing.

        This is the most valuable use: POLYGOD learns from every error it fixes.
        """
        if not self.available:
            return False
        try:
            content = (
                f"ERROR in {component}:\n{error}\n\n"
                f"FIX APPLIED:\n{fix}\n\n"
                f"Date: {datetime.now(timezone.utc).isoformat()}"
            )
            # Use CLI to add to palace (most reliable)
            result = subprocess.run(
                [
                    "mempalace",
                    "mine",
                    "-",
                    "--wing",
                    "wing_errors",
                    "--room",
                    component.lower().replace(" ", "-"),
                    "--palace",
                    self.palace_path,
                ],
                input=content,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"MemPalace error storage failed: {e}")
            return False

    async def remember_decision(
        self, decision: str, rationale: str, component: str
    ) -> bool:
        """Store an architecture/operational decision."""
        if not self.available:
            return False
        try:
            content = (
                f"DECISION: {decision}\n\n"
                f"RATIONALE: {rationale}\n\n"
                f"Component: {component}\n"
                f"Date: {datetime.now(timezone.utc).isoformat()}"
            )
            result = subprocess.run(
                [
                    "mempalace",
                    "mine",
                    "-",
                    "--wing",
                    "wing_polygod",
                    "--room",
                    "decisions",
                    "--palace",
                    self.palace_path,
                ],
                input=content,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"MemPalace decision storage failed: {e}")
            return False

    async def get_error_fix(self, error_message: str) -> str | None:
        """
        Look up a past error fix. Used by self-healing engine before
        attempting an LLM fix — much faster and more reliable.
        """
        results = await self.search(
            error_message[:200],
            wing="wing_errors",
            top_k=3,
        )
        if results:
            return str(results[0].get("content", ""))
        return None

    async def get_operator_preferences(self) -> str:
        """Load operator preferences for agent context injection."""
        results = await self.search(
            "operator preferences settings",
            wing="wing_operator",
            top_k=5,
        )
        if not results:
            return ""
        return "\n".join(r.get("content", "") for r in results)

    async def wake_up_context(self) -> str:
        """
        Generate a wake-up context string for injection into agent prompts.
        Equivalent to `mempalace wake-up` but returns a string.
        """
        if not self.available:
            return ""
        try:
            result = subprocess.run(
                ["mempalace", "wake-up", "--palace", self.palace_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout[:2000] if result.returncode == 0 else ""
        except Exception as e:
            logger.warning(f"MemPalace wake-up failed: {e}")
            return ""


# Singleton
mempalace_bridge = MemPalaceBridge()

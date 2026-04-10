"""
SELF-IMPROVING MEMORY LOOP — God-Tier autonomous evolution.

Connects Mem0 long-term memory with AutoResearchLab for weekly self-improvement:
- remember_node(): auto-write EVERY node output to Mem0 (including WhaleContext)
- hindsight_replay(): weekly replay of last 7 days trades (200 memories)
- notebooklm_reflection(): Sunday podcast-style reflection → 5 mutation instructions
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

try:
    from mem0 import Memory as _Mem0Memory  # mem0ai package exports Memory, not Mem0

    _HAS_MEM0 = True
except ImportError:
    _HAS_MEM0 = False

from src.backend.config import settings
from src.backend.llm_router import router

try:
    from langsmith import traceable
except ImportError:

    def traceable(*args, **kwargs):
        def decorator(fn):
            return fn

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


logger = logging.getLogger(__name__)

# Initialize Mem0 client (graceful fallback if mem0 not installed)
mem0 = None
if _HAS_MEM0:
    try:
        import json as _json

        _mem0_config = _json.loads(settings.MEM0_CONFIG)
        mem0 = _Mem0Memory.from_config(_mem0_config)
    except Exception as _e:
        logger.warning(f"Mem0 initialization failed in memory loop: {_e}")


class SelfImprovingMemoryLoop:
    """Autonomous memory loop — writes every node output to Mem0,
    runs weekly hindsight replay and NotebookLM-style reflections
    to generate mutation instructions for AutoResearchLab."""

    def __init__(self):
        self.user_id = "polygod_swarm"

    @traceable
    async def remember_node(self, state, node_name: str):
        """Auto-remember on EVERY node — this is the core of self-improvement"""
        if mem0 is None:
            logger.debug(f"Memory loop: Mem0 not available, skipping {node_name}")
            return state

        try:
            verdict = state.get("verdict", "")
            confidence = state.get("confidence", 0)
            execution_result = state.get("execution_result", {})
            pnl = 0.0
            if isinstance(execution_result, dict):
                pnl = execution_result.get("pnl", 0)
                if pnl == 0:
                    pnl = execution_result.get("result", {}).get("pnl", 0)

            # God-tier memory format: includes WhaleContext for pattern recognition
            memory_text = (
                f"[{datetime.utcnow().isoformat()}] "
                f"Node: {node_name} | "
                f"Market: {state.get('market_id')} | "
                f"Verdict: {verdict[:200]} | "
                f"Confidence: {confidence}% | "
                f"PnL: {pnl} | "
                f"WhaleContext: {state.get('whale_context', '')[:200]}"
            )

            mem0.add(
                memory_text,
                user_id=self.user_id,
                metadata={
                    "node": node_name,
                    "market_id": state.get("market_id", "unknown"),
                    "confidence": confidence,
                    "pnl": pnl,
                },
            )
            logger.debug(
                f"Memory loop: wrote {node_name} output to Mem0 "
                f"(confidence={confidence}, pnl={pnl})"
            )
        except Exception as e:
            logger.debug(f"Memory loop remember_node failed: {e}")

        return state

    async def hindsight_replay(self):
        """Weekly hindsight replay of last 7 days — score trades, extract lessons."""
        if mem0 is None:
            logger.warning("Memory loop: Mem0 not available, skipping hindsight replay")
            return "Mem0 not available"

        try:
            logger.info("=== MEMORY LOOP: Weekly Hindsight Replay ===")
            memories = mem0.search(
                "trade OR debate OR tournament OR execution",
                user_id=self.user_id,
                limit=200,
            )
            logger.info(f"Hindsight replay: found {len(memories)} memories")

            # Generate hindsight summary via LLM
            summary_prompt = (
                f"Summarize key lessons, winning patterns, and mistakes from these memories: "
                f"{memories[:50]}"
            )
            summary = await router.route(
                summary_prompt, "Hindsight_Replay", priority="cheap"
            )

            # Store the insight
            mem0.add(
                f"Hindsight Weekly Replay Summary: {summary}",
                user_id=self.user_id,
            )
            logger.info(f"=== Hindsight Replay Complete: {len(summary)} chars ===")
            return summary
        except Exception as e:
            logger.error(f"Hindsight replay failed: {e}")
            return f"Hindsight replay failed: {e}"

    async def notebooklm_reflection(self):
        """Sunday NotebookLM-style podcast reflection → 5 concrete mutations"""
        if mem0 is None:
            logger.warning("Memory loop: Mem0 not available, skipping reflection")
            return []

        try:
            logger.info("=== MEMORY LOOP: NotebookLM Reflection ===")

            # Lazy import to avoid circular dependency
            from src.backend.autoresearch_lab import autoresearch_lab

            memories = mem0.search("all", user_id=self.user_id, limit=100)
            logger.info(f"NotebookLM reflection: {len(memories)} memories loaded")

            week_str = datetime.utcnow().strftime("%Y-%m-%d")
            prompt = (
                f"Act as NotebookLM. Generate a 2-minute podcast episode: "
                f'"POLYGOD Weekly Evolution - {week_str}". '
                f"Discuss best trades, worst edges, whale copy patterns, "
                f"and self-improvement opportunities. At the end, output ONLY "
                f"a JSON array of exactly 5 targeted mutation instructions "
                f"for the AutoResearchLab (e.g. Kelly fraction tweaks, "
                f"new hedge rules, niche filters, confidence thresholds). "
                f"Memories: {memories}"
            )
            reflection = await router.route(
                prompt, "NotebookLM_Reflection", priority="cheap"
            )
            logger.info(
                f"NotebookLM reflection LLM response received ({len(reflection)} chars)"
            )

            # Parse mutation instructions
            instructions = []
            try:
                instructions = json.loads(reflection)
            except json.JSONDecodeError:
                # Fallback: try to find JSON array in response
                json_start = reflection.find("[")
                json_end = reflection.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    instructions = json.loads(reflection[json_start:json_end])
                else:
                    logger.warning("NotebookLM: JSON parse failed, raw output saved")
                    raw_preview = reflection[:500]
                    mem0.add(
                        f"NotebookLM Reflection failed to parse — raw output saved: {raw_preview}",
                        user_id=self.user_id,
                    )
                    return []

            # Apply 5 mutations to AutoResearchLab
            mutations_applied = 0
            for instr in instructions[:5]:
                try:
                    await autoresearch_lab.mutate_and_evolve(
                        {"evolution_instruction": instr}
                    )
                    mutations_applied += 1
                except Exception as e:
                    logger.warning(
                        f"Mutation failed for instruction: {instr[:50]}... — {e}"
                    )

            # Log completion
            completion_msg = (
                f"NotebookLM Reflection: {mutations_applied}/{len(instructions)} "
                f"mutations promoted to AutoResearchLab"
            )
            logger.info(f"=== {completion_msg} ===")

            if mem0:
                try:
                    mem0.add(completion_msg, user_id=self.user_id)
                except Exception:
                    pass

            return instructions
        except Exception as e:
            logger.error(f"NotebookLM reflection failed: {e}")
            return []


memory_loop = SelfImprovingMemoryLoop()


# ==================== FORGETTING ENGINE ====================
class ForgettingEngine:
    """
    Intelligent memory forgetting system with TTL tiers.

    Tiers:
    - high_utility: 90 days (whale strategies, high-PnL trades)
    - medium: 30 days
    - low: 7 days (transient debate noise)
    """

    def __init__(self):
        self.ttl_tiers = {
            "high_utility": timedelta(days=90),
            "medium": timedelta(days=30),
            "low": timedelta(days=7),
        }

    async def prune(self) -> dict[str, Any]:
        """
        Score and forget irrelevant data based on utility and TTL.

        Returns:
            Dictionary with pruned count and status
        """
        if mem0 is None:
            logger.warning("ForgettingEngine: Mem0 not available, skipping prune")
            return {"status": "skipped", "message": "Mem0 not available"}

        try:
            logger.info("=== FORGETTING ENGINE: Pruning low-signal memories ===")

            # Fetch recent memories
            memories = mem0.search("all", user_id="polygod_swarm", limit=500)
            pruned_count = 0

            for mem in memories:
                try:
                    # Calculate importance score
                    score = self._importance_score(mem)

                    # Get memory timestamp
                    mem_timestamp_str = mem.get("metadata", {}).get("timestamp", "")
                    if not mem_timestamp_str:
                        continue

                    mem_timestamp = datetime.fromisoformat(mem_timestamp_str)
                    tier = mem.get("metadata", {}).get("tier", "low")
                    ttl = self.ttl_tiers.get(tier, timedelta(days=7))

                    # Check if should prune (low score OR TTL expired)
                    should_prune = (
                        score < 0.3 or (mem_timestamp + ttl) < datetime.utcnow()
                    )

                    if should_prune:
                        mem0.delete(mem["id"], user_id="polygod_swarm")
                        pruned_count += 1
                        logger.debug(
                            f"ForgettingEngine: Pruned memory {mem['id'][:20]}..."
                        )

                except Exception as e:
                    logger.debug(f"ForgettingEngine: Error processing memory: {e}")
                    continue

            logger.info(f"ForgettingEngine: Pruned {pruned_count} memories")
            return {"status": "success", "pruned_count": pruned_count}

        except Exception as e:
            logger.error(f"ForgettingEngine: Prune failed: {e}")
            return {"status": "error", "message": str(e)}

    def _importance_score(self, mem: dict) -> float:
        """
        Calculate importance score for a memory.

        Formula: Relevance × Recency × Utility (PnL, confidence, whale usage)

        Args:
            mem: Memory dictionary with metadata

        Returns:
            Score between 0 and 1
        """
        try:
            # Recency factor: newer = higher score
            mem_timestamp_str = mem.get("metadata", {}).get("timestamp", "")
            if not mem_timestamp_str:
                return 0.0

            mem_timestamp = datetime.fromisoformat(mem_timestamp_str)
            days_ago = (datetime.utcnow() - mem_timestamp).days
            recency = 1.0 / (1.0 + days_ago)

            # Utility factor: PnL + confidence
            pnl = mem.get("metadata", {}).get("pnl", 0)
            confidence = mem.get("metadata", {}).get("confidence", 0)
            utility = pnl + (confidence / 100.0)

            # Combined score (tunable factor of 0.8)
            score = recency * utility * 0.8

            return min(1.0, max(0.0, score))

        except Exception:
            return 0.0


forgetting_engine = ForgettingEngine()

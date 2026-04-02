"""
SELF-IMPROVING MEMORY LOOP — God-Tier autonomous evolution.

Connects Mem0 long-term memory with AutoResearchLab for weekly self-improvement:
- remembver_node(): auto-write every node output to Mem0
- hindsight_replay(): weekly replay of last 7 days trades
- notebooklm_reflection(): Sunday podcast-style reflection → mutation instructions
"""

import json
import logging
from datetime import datetime

try:
    from mem0 import Mem0
except ImportError:
    Mem0 = None

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
if Mem0 is not None:
    try:
        mem0_config = json.loads(settings.MEM0_CONFIG)
        mem0 = Mem0.from_config(mem0_config)
    except Exception as e:
        logger.warning(f"Mem0 initialization failed in memory loop: {e}")


class SelfImprovingMemoryLoop:
    """Autonomous memory loop — writes every node output to Mem0,
    runs weekly hindsight replay and NotebookLM-style reflections
    to generate mutation instructions for AutoResearchLab."""

    def __init__(self):
        self.user_id = "polygod_swarm"

    @traceable
    async def remember_node(self, state, node_name: str):
        """Auto-write EVERY node output to Mem0."""
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

            memory_text = (
                f"Node {node_name} at {datetime.utcnow().isoformat()}: "
                f"{verdict[:200]} | Confidence {confidence}% | PnL {pnl}"
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
        """Weekly replay of last 7 days — score trades, extract lessons."""
        if mem0 is None:
            logger.warning("Memory loop: Mem0 not available, skipping hindsight replay")
            return "Mem0 not available"

        try:
            logger.info("=== MEMORY LOOP: Weekly Hindsight Replay ===")
            memories = mem0.search(
                "trade OR debate OR tournament OR execution",
                user_id=self.user_id,
                limit=100,
            )
            logger.info(f"Hindsight replay: found {len(memories)} memories")

            # Generate hindsight summary via LLM
            summary = await self._generate_hindsight_summary(memories)

            # Store the insight
            mem0.add(
                f"Hindsight weekly replay at {datetime.utcnow().isoformat()}: {summary}",
                user_id=self.user_id,
            )
            logger.info(f"=== Hindsight Replay Complete: {len(summary)} chars ===")
            return summary
        except Exception as e:
            logger.error(f"Hindsight replay failed: {e}")
            return f"Hindsight replay failed: {e}"

    async def notebooklm_reflection(self):
        """Sunday NotebookLM-style podcast reflection — generates mutation instructions."""
        if mem0 is None:
            logger.warning("Memory loop: Mem0 not available, skipping reflection")
            return []

        try:
            logger.info("=== MEMORY LOOP: NotebookLM Reflection ===")

            # Lazy import to avoid circular dependency
            from src.backend.autoresearch_lab import autoresearch_lab

            memories = mem0.search("all", user_id=self.user_id, limit=50)
            logger.info(f"NotebookLM reflection: {len(memories)} memories loaded")

            week_str = datetime.utcnow().strftime("%Y-%m-%d")
            prompt = (
                "You are NotebookLM, creating a podcast episode titled "
                f'"POLYGOD Weekly Reflection — Week of {week_str}".\n'
                "Two hosts discuss the week's trading activity "
                "based on these memories:\n"
                f"{json.dumps(memories[:20], default=str)[:3000]}\n\n"
                "Extract exactly 5 concrete mutation instructions for "
                "an AutoResearchLab that improves:\n"
                "- Kelly tweaks (e.g., adjust fraction by X% if pattern Y)\n"
                "- Hedge rules (e.g., always hedge when condition Z)\n"
                "- Niche filters (e.g., ignore markets with volume < $N)\n"
                "- Risk guard adjustments\n"
                "- Agent prompt improvements\n\n"
                "Return ONLY a JSON array of 5 strings, nothing else."
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
                # Try to find JSON array in response
                json_start = reflection.find("[")
                json_end = reflection.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    instructions = json.loads(reflection[json_start:json_end])
                else:
                    # Fallback: parse line by line
                    instructions = [
                        line.strip().lstrip("0123456789.-) ")
                        for line in reflection.strip().split("\n")
                        if line.strip() and len(line.strip()) > 10
                    ]
                    instructions = instructions[:5]
            except json.JSONDecodeError as e:
                logger.warning(f"NotebookLM: JSON parse failed ({e}), using fallback")
                instructions = [f"Review week of {week_str}: {reflection[:200]}"]

            # Apply mutations to AutoResearchLab
            mutations_applied = 0
            for instr in instructions:
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
                f"NotebookLM reflection complete: {mutations_applied}/{len(instructions)} "
                f"mutations promoted"
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

    async def _generate_hindsight_summary(self, memories: list) -> str:
        """Generate a concise hindsight summary from memories via LLM."""
        try:
            memories_text = json.dumps(memories[:10], default=str)[:2000]
            prompt = f"""Summarize the key hindsight lessons from these trading memories.
Focus on:
1. What went well (wins, good timing, correct predictions)
2. What went wrong (losses, missed signals, bad timing)
3. Patterns that should be reinforced or avoided
4. Concrete adjustments for next week

Memories:
{memories_text}

Be concise — 3-5 sentences max."""

            return await router.route(prompt, "Hindsight_Summary", priority="cheap")
        except Exception as e:
            logger.warning(f"Hindsight summary generation failed: {e}")
            return f"Hindsight summary generation failed: {e}"


memory_loop = SelfImprovingMemoryLoop()

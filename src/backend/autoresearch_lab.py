# src/backend/autoresearch_lab.py
"""
AutoResearch Lab — Karpathy-style self-improving mutation loop.

Wired to Polymarket via LangGraph cyclic swarm:
1. Read current strategy + evolution instructions from Mem0
2. LLM proposes mutation (Puter.js priority for cost efficiency)
3. Apply edit + commit to git
4. Run parallel paper tournament on 50 variants
5. Darwinian decision: keep if sharpe > 2.0 AND pnl > 0, else git reset
"""

import logging
import os
from typing import Dict

import git

from src.backend.llm_router import router
from src.backend.parallel_tournament import parallel_paper_tournament

logger = logging.getLogger(__name__)

# Mem0 import with graceful fallback (matches existing codebase pattern)
try:
    from mem0 import Memory

    mem0_config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "autoresearch_memory",
                "host": "localhost",
                "port": 6333,
            },
        },
    }
    mem0_instance = Memory.from_config(mem0_config)
except Exception as e:
    logger.warning(f"Mem0 initialization failed: {e}, using local memory fallback")
    mem0_instance = None


class AutoResearchLab:
    """Karpathy-style auto-research lab for self-improving trading strategies."""

    SHARPE_THRESHOLD = 2.0
    PNL_THRESHOLD = 0.0
    MAX_MUTATION_RETRIES = 3

    def __init__(self):
        self.repo = self._init_repo()
        self.strategy_file = os.path.join(
            os.path.dirname(__file__), "strategies", "micro_niche_strategy.py"
        )
        self.mem0 = mem0_instance

    def _init_repo(self) -> git.Repo:
        """Initialize git repo with error handling."""
        try:
            return git.Repo(os.path.join(os.path.dirname(__file__), "..", ".."))
        except git.InvalidGitRepositoryError:
            logger.warning("Not a git repository — git mutations disabled")
            return None
        except Exception as e:
            logger.warning(f"Git repo init failed: {e}")
            return None

    def _mem0_add(self, content: str, user_id: str = "evolution_lab"):
        """Add to mem0 with graceful fallback."""
        if self.mem0:
            try:
                self.mem0.add(content, user_id=user_id)
            except Exception as e:
                logger.debug(f"mem0 add failed: {e}")

    def _mem0_search(self, query: str, user_id: str = "evolution_lab") -> str:
        """Search mem0 with graceful fallback."""
        if self.mem0:
            try:
                results = self.mem0.search(query, user_id=user_id)
                if results:
                    return "\n".join([str(r.get("memory", r)) for r in results[:5]])
            except Exception as e:
                logger.debug(f"mem0 search failed: {e}")
        return ""

    def _read_strategy(self) -> str:
        """Read current strategy code."""
        try:
            with open(self.strategy_file, "r") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Strategy file not found: {self.strategy_file}")
            return (
                "# Strategy not found — use default\n"
                "KELLY_FRACTION = 0.02\n"
                "HEDGE_THRESHOLD = 0.95\n"
            )

    def _write_strategy(self, code: str):
        """Write new strategy code."""
        os.makedirs(os.path.dirname(self.strategy_file), exist_ok=True)
        with open(self.strategy_file, "w") as f:
            f.write(code)

    def _commit_mutation(self, mutation_summary: str) -> bool:
        """Commit mutation to git."""
        if not self.repo:
            logger.info("Git not available — skipping commit")
            return False
        try:
            self.repo.index.add(
                [os.path.relpath(self.strategy_file, self.repo.working_dir)]
            )
            self.repo.index.commit(f"AutoResearch mutation: {mutation_summary[:80]}")
            logger.info(f"Git commit: {mutation_summary[:80]}")
            return True
        except Exception as e:
            logger.error(f"Git commit failed: {e}")
            return False

    def _reset_mutation(self) -> bool:
        """Reset last mutation via git."""
        if not self.repo:
            logger.info("Git not available — cannot reset")
            return False
        try:
            self.repo.git.reset("--hard", "HEAD~1")
            logger.info("Git reset: mutation discarded")
            return True
        except Exception as e:
            logger.error(f"Git reset failed: {e}")
            return False

    async def _generate_mutation(self, current_code: str) -> str:
        """Generate mutation proposal via LLM router."""
        program_instructions = self._mem0_search(
            "evolution_instructions", user_id="polygod_swarm"
        ) or (
            "Mutate Kelly fraction, hedge thresholds, and niche detection rules "
            "for weather/twitter micro-niches. Maximize Sharpe ratio. "
            "Keep changes focused and incremental. One parameter or rule at a time."
        )

        prompt = f"""You are the AutoResearch Lab — a Karpathy-style self-improving AI.

Your task: Propose ONE targeted edit to improve this Polymarket trading strategy.

Evolution Instructions:
{program_instructions}

Current Strategy Code:
```python
{current_code}
```

Rules:
1. Only modify parameters or logic BELOW the # MUTATION_POINT marker
2. Make ONE focused change — do not rewrite everything
3. Explain your change in a comment at the top
4. Return ONLY the modified code section (not the entire file)

Propose your mutation:"""

        response = await router.route(prompt, "AutoResearcher", priority="cheap")
        return str(response)

    def _apply_mutation(self, current_code: str, mutation: str) -> str:
        """Apply mutation to strategy code.

        Handles three cases:
        1. Mutation contains full file — use as-is
        2. Mutation contains section below MUTATION_POINT — replace below marker
        3. Fallback — append mutation
        """
        mutation_marker = "# MUTATION_POINT"
        mutation_clean = mutation.strip()

        # Check if mutation contains the full file
        if "import" in mutation_clean and "KELLY" in mutation_clean:
            # Full file mutation — keep header, replace body
            header_lines = []
            for line in current_code.split("\n"):
                header_lines.append(line)
                if mutation_marker in line:
                    break

            new_code = "\n".join(header_lines) + "\n" + mutation_clean
            return new_code

        # Check if mutation is a partial edit (just the mutable section)
        if mutation_marker in current_code:
            idx = current_code.index(mutation_marker)
            # Find the end of the marker line
            newline_idx = (
                current_code.index("\n", idx)
                if "\n" in current_code[idx:]
                else len(current_code)
            )
            header = current_code[: newline_idx + 1]
            new_code = header + "\n" + mutation_clean
            return new_code

        # Fallback — append
        return current_code + "\n\n# AutoResearch Mutation:\n" + mutation_clean

    async def mutate_and_evolve(self, state: Dict) -> Dict:
        """
        Main Karpathy loop: mutate → test → select.

        Steps:
        1. Read current strategy + Mem0 instructions
        2. LLM proposes mutation (Puter.js cheap priority)
        3. Apply edit + commit
        4. Run parallel paper tournament (50 variants)
        5. Darwinian decision: keep winners, discard losers
        """
        logger.info("=" * 60)
        logger.info("AUTORESEARCH LAB: Starting Karpathy mutation loop")
        logger.info("=" * 60)

        # Step 1: Read current strategy
        current_code = self._read_strategy()
        logger.info(f"Loaded strategy: {len(current_code)} chars")

        # Step 2-3: Generate and apply mutation
        try:
            mutation = await self._generate_mutation(current_code)
            logger.info(f"Mutation generated: {mutation[:100]}...")
        except Exception as e:
            logger.error(f"Mutation generation failed: {e}")
            # Return state unchanged if LLM fails
            return state

        new_code = self._apply_mutation(current_code, mutation)

        # Step 3: Write and commit
        self._write_strategy(new_code)
        mutation_summary = mutation[:100] if mutation else "unknown"
        committed = self._commit_mutation(mutation_summary)

        if not committed:
            logger.info("Mutation not committed — continuing with in-memory version")

        # Step 4: Run parallel paper tournament
        try:
            state = await parallel_paper_tournament(state)
            logger.info("Parallel tournament completed")
        except Exception as e:
            logger.error(f"Parallel tournament failed: {e}")
            # Reset on tournament failure
            if committed:
                self._reset_mutation()
            return state

        # Step 5: Darwinian decision
        final_decision = state.get("final_decision", {})
        tournament_best_pnl = final_decision.get("tournament_best_pnl", 0)
        evolution_best = state.get("evolution_best", {})
        sharpe = evolution_best.get(
            "score", 0
        )  # Using tournament score as proxy for sharpe

        # Also check decision dict for pnl
        pnl = tournament_best_pnl or final_decision.get("pnl", 0)

        logger.info(f"Darwinian decision: sharpe={sharpe:.3f}, pnl={pnl:.2f}")
        logger.info(
            f"Thresholds: sharpe > {self.SHARPE_THRESHOLD}, pnl > {self.PNL_THRESHOLD}"
        )

        if sharpe > self.SHARPE_THRESHOLD and pnl > self.PNL_THRESHOLD:
            # Winner — keep mutation
            self._mem0_add(
                f"WINNER mutation kept: {mutation_summary} | "
                f"sharpe={sharpe:.3f}, pnl={pnl:.2f}",
                user_id="evolution_lab",
            )
            logger.info(f"MUTATION KEPT: sharpe={sharpe:.3f}, pnl={pnl:.2f}")
            state["evolution_status"] = "mutation_kept"
        else:
            # Loser — discard mutation
            if committed:
                self._reset_mutation()
            else:
                # If not committed, restore original code
                self._write_strategy(current_code)

            self._mem0_add(
                f"Mutation discarded: {mutation_summary} | "
                f"sharpe={sharpe:.3f}, pnl={pnl:.2f}",
                user_id="evolution_lab",
            )
            logger.info(f"MUTATION DISCARDED: sharpe={sharpe:.3f}, pnl={pnl:.2f}")
            state["evolution_status"] = "mutation_discarded"

        # Update state with evolution metadata
        state["evolution_lab_result"] = {
            "mutation_summary": mutation_summary,
            "sharpe": sharpe,
            "pnl": pnl,
            "kept": sharpe > self.SHARPE_THRESHOLD and pnl > self.PNL_THRESHOLD,
            "committed": committed,
        }

        logger.info("AUTORESEARCH LAB: Karpathy loop complete")
        return state


# Singleton instance
autoresearch_lab = AutoResearchLab()

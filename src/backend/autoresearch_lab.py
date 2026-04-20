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

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict

try:
    import git as _git

    _GIT_AVAILABLE = True
except ImportError:
    _git = None
    _GIT_AVAILABLE = False

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

    def _init_repo(self):
        """Initialize git repo with error handling. Returns None if git unavailable."""
        if not _GIT_AVAILABLE:
            logger.warning("gitpython not installed — git mutations disabled")
            return None
        try:
            return _git.Repo(os.path.join(os.path.dirname(__file__), "..", ".."))
        except _git.InvalidGitRepositoryError:
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
            self.repo.index.add([os.path.relpath(self.strategy_file, self.repo.working_dir)])
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
                current_code.index("\n", idx) if "\n" in current_code[idx:] else len(current_code)
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

        # FIX M-7: Validate Python syntax BEFORE writing to disk or committing.
        import ast as _ast

        try:
            _ast.parse(new_code)
        except SyntaxError as syntax_err:
            logger.error(
                "AutoResearchLab: mutation produced invalid Python — discarding. SyntaxError: %s",
                syntax_err,
            )
            # Can't call _mem0_add here as self doesn't have access to memory_loop directly
            # Log the discard event
            logger.warning(
                f"Mutation DISCARDED (SyntaxError): {mutation[:100] if mutation else 'unknown'}"
            )
            state["evolution_status"] = "mutation_syntax_error"
            return state

        # Step 3: Write and commit (only reached if syntax is valid)
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
        sharpe = evolution_best.get("score", 0)  # Using tournament score as proxy for sharpe

        # Also check decision dict for pnl
        pnl = tournament_best_pnl or final_decision.get("pnl", 0)

        logger.info(f"Darwinian decision: sharpe={sharpe:.3f}, pnl={pnl:.2f}")
        logger.info(f"Thresholds: sharpe > {self.SHARPE_THRESHOLD}, pnl > {self.PNL_THRESHOLD}")

        if sharpe > self.SHARPE_THRESHOLD and pnl > self.PNL_THRESHOLD:
            # Winner — keep mutation
            self._mem0_add(
                f"WINNER mutation kept: {mutation_summary} | sharpe={sharpe:.3f}, pnl={pnl:.2f}",
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
                f"Mutation discarded: {mutation_summary} | sharpe={sharpe:.3f}, pnl={pnl:.2f}",
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

    async def run_weekly_backtest(self) -> dict:
        """
        Self-evolving weekly backtest loop.

        Steps:
        1. Pull top 10 tracked markets from DB
        2. Stream last 30 days of candles for each (Polars + HF streaming)
        3. Run Chronos forecast at the T-7d point (hindcast)
        4. Compare forecast to actual T+0 outcome
        5. Score accuracy per market category
        6. Write accuracy scores to Mem0 → notebooklm_reflection picks them up Sunday night
           and auto-generates mutation instructions to improve category-specific sizing
        """
        logger.info("=" * 60)
        logger.info("AUTORESEARCH BACKTEST: Starting weekly accuracy sweep")
        logger.info("=" * 60)

        import numpy as np
        import torch
        from sqlalchemy import select

        from src.backend.database import async_session_factory
        from src.backend.db_models import Market
        from src.backend.tools.kronos_polydata import (
            _build_candles_from_batches,
            _get_chronos_pipeline,
            _stream_hf_batches,
        )

        results = []
        category_scores: dict[str, list[float]] = {}

        # ── Pull top 10 markets ──────────────────────────────────────────────
        async with async_session_factory() as db:
            result = await db.execute(
                select(Market)
                .where(Market.is_active == True)  # noqa: E712
                .order_by(Market.volume_7d.desc())
                .limit(10)
            )
            markets = result.scalars().all()

        if not markets:
            logger.warning("Backtest: no active markets found, skipping")
            return {"status": "skipped", "reason": "no_markets"}

        pipeline = await _get_chronos_pipeline()
        if pipeline is None:
            logger.warning("Backtest: Chronos pipeline unavailable, skipping")
            return {"status": "skipped", "reason": "chronos_unavailable"}

        for market in markets:
            market_slug = market.slug or market.id
            # Infer category from title keywords (extends as needed)
            title_lower = market.title.lower()
            if any(
                k in title_lower for k in ["btc", "eth", "crypto", "bitcoin", "ethereum", "sol"]
            ):
                category = "crypto"
            elif any(
                k in title_lower
                for k in ["election", "president", "senate", "vote", "trump", "biden"]
            ):
                category = "politics"
            elif any(
                k in title_lower for k in ["nba", "nfl", "soccer", "championship", "league", "cup"]
            ):
                category = "sports"
            elif any(k in title_lower for k in ["fed", "rate", "gdp", "inflation", "economy"]):
                category = "macro"
            else:
                category = "other"

            try:
                logger.info("Backtest: processing %s (category=%s)", market_slug, category)

                # Stream 30 days of candles
                batches = await _stream_hf_batches(
                    market_slug=market_slug,
                    timeout_seconds=45,
                    max_batches=500,  # larger window for 30-day backtest
                )
                candles = _build_candles_from_batches(
                    batches,
                    market_slug=market_slug,
                    timeframe="1h",
                    max_candles=720,  # 30 days × 24 hours
                )

                if len(candles) < 50:
                    logger.info(
                        "Backtest: insufficient history for %s (%d candles)",
                        market_slug,
                        len(candles),
                    )
                    continue

                close_prices = candles["close"].to_list()

                # Split: use first 23 days as context, last 7 days as ground truth
                # This simulates a T-7d forecast vs T+0 actual
                split_idx = max(10, len(close_prices) - 168)  # 168 = 7 days × 24h
                context_prices = close_prices[:split_idx]
                actual_prices = close_prices[split_idx:]

                if len(context_prices) < 10 or len(actual_prices) < 1:
                    continue

                # Run Chronos hindcast
                context_tensor = torch.tensor(context_prices[-512:], dtype=torch.float32).unsqueeze(
                    0
                )
                raw_forecast = await asyncio.to_thread(
                    pipeline.predict,
                    context_tensor,
                    len(actual_prices),
                )

                forecast_median = np.median(raw_forecast[0].numpy(), axis=0)
                actual_array = np.array(actual_prices)

                # Score: mean absolute error, direction accuracy, calibration
                mae = float(np.mean(np.abs(forecast_median - actual_array)))
                direction_correct = int(
                    np.sign(forecast_median[-1] - context_prices[-1])
                    == np.sign(actual_prices[-1] - context_prices[-1])
                )
                # Calibration: was actual within ±0.05 of median forecast?
                within_5pct = int(abs(float(forecast_median[-1]) - float(actual_prices[-1])) < 0.05)

                accuracy_score = (
                    (direction_correct * 0.5)
                    + (within_5pct * 0.3)
                    + max(0.0, (1.0 - mae * 10) * 0.2)
                )
                accuracy_score = round(min(1.0, max(0.0, accuracy_score)), 4)

                market_result = {
                    "market_id": market.id,
                    "market_slug": market_slug,
                    "category": category,
                    "candles_used": len(close_prices),
                    "mae": round(mae, 4),
                    "direction_correct": bool(direction_correct),
                    "within_5pct": bool(within_5pct),
                    "accuracy_score": accuracy_score,
                }
                results.append(market_result)

                if category not in category_scores:
                    category_scores[category] = []
                category_scores[category].append(accuracy_score)

                logger.info(
                    "Backtest %s: score=%.3f MAE=%.4f direction=%s",
                    market_slug,
                    accuracy_score,
                    mae,
                    bool(direction_correct),
                )

            except Exception as exc:
                logger.warning("Backtest: failed for %s: %s", market_slug, exc)
                continue

        if not results:
            return {"status": "complete", "markets_scored": 0}

        # ── Compute category-level summary ───────────────────────────────────
        category_summary = {
            cat: {
                "avg_accuracy": round(sum(scores) / len(scores), 4),
                "n_markets": len(scores),
                "best": round(max(scores), 4),
                "worst": round(min(scores), 4),
            }
            for cat, scores in category_scores.items()
        }

        overall_accuracy = round(sum(r["accuracy_score"] for r in results) / len(results), 4)

        backtest_summary = {
            "run_date": datetime.now(timezone.utc).isoformat(),
            "markets_scored": len(results),
            "overall_accuracy": overall_accuracy,
            "by_category": category_summary,
            "detail": results,
        }

        logger.info(
            "BACKTEST COMPLETE: %d markets, overall_accuracy=%.3f",
            len(results),
            overall_accuracy,
        )
        logger.info("Category breakdown: %s", category_summary)

        # ── Write to Mem0 so notebooklm_reflection picks it up Sunday ────────
        # notebooklm_reflection already searches mem0 for "all" — these records
        # will surface in the Sunday podcast and generate mutation instructions
        self._mem0_add(
            f"BACKTEST RESULTS {backtest_summary['run_date']}: "
            f"overall_accuracy={overall_accuracy:.3f} | "
            f"by_category={category_summary} | "
            f"Recommend: increase Kelly fraction for categories accuracy > 0.7, "
            f"reduce for categories accuracy < 0.4",
            user_id="evolution_lab",
        )

        # Write a separate record per low-performing category so the LLM
        # gets explicit, actionable mutation targets
        for cat, stats in category_summary.items():
            avg = stats["avg_accuracy"]
            if avg < 0.4:
                self._mem0_add(
                    f"BACKTEST LOW ACCURACY: category={cat} avg={avg:.3f} "
                    f"— MUTATION INSTRUCTION: reduce position sizing for {cat} markets "
                    f"by 30%, widen confidence thresholds, add contrarian signal weight",
                    user_id="evolution_lab",
                )
            elif avg > 0.7:
                self._mem0_add(
                    f"BACKTEST HIGH ACCURACY: category={cat} avg={avg:.3f} "
                    f"— MUTATION INSTRUCTION: increase Kelly fraction for {cat} markets "
                    f"by 15%, tighten entry threshold, trust Kronos signal more",
                    user_id="evolution_lab",
                )

        return backtest_summary

    def _mem0_add(self, content: str, user_id: str = "autoresearch_lab") -> None:
        """Helper method to add to Mem0 with graceful fallback."""
        try:
            if mem0_instance:
                mem0_instance.add(content, user_id=user_id)
            else:
                logger.debug("Mem0 unavailable, skipping: %s", content[:100])
        except Exception as e:
            logger.warning("Mem0 write failed: %s", e)


# Singleton instance
autoresearch_lab = AutoResearchLab()

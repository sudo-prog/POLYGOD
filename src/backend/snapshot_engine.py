"""
SNAPSHOT ENGINE — Full code + state snapshot system for rollback and fine-tuning.

Provides:
- Git-based code snapshots with commit messages
- LangGraph state checkpoints using SqliteSaver
- Mem0 memory snapshots for pattern recognition
- Rollback capability to restore code to peak states
"""

import logging
from datetime import datetime
from typing import Any

import git

logger = logging.getLogger(__name__)

# Import memory_loop for Mem0 integration
try:
    from src.backend.self_improving_memory_loop import memory_loop
except ImportError:
    memory_loop = None


class SnapshotEngine:
    """Full snapshot system for code + state rollback and fine-tuning."""

    def __init__(self):
        self.repo = git.Repo(".")
        self.checkpointer = None
        self._init_checkpointer()

    def _init_checkpointer(self):
        """Initialize LangGraph checkpointer with graceful fallback."""
        try:
            import sqlite3

            from langgraph.checkpoint.sqlite import SqliteSaver

            conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
            conn.close()
            self.checkpointer = SqliteSaver(conn)
            logger.info("SnapshotEngine: SqliteSaver checkpointer initialized")
        except Exception as e:
            logger.warning(f"SnapshotEngine: SqliteSaver not available: {e}")
            try:
                from langgraph.checkpoint.memory import MemorySaver

                self.checkpointer = MemorySaver()
                logger.info("SnapshotEngine: MemorySaver fallback initialized")
            except Exception as e2:
                logger.error(f"SnapshotEngine: No checkpointer available: {e2}")

    async def take_snapshot(
        self, state: dict[str, Any], label: str = "auto"
    ) -> dict[str, Any]:
        """
        Take a full code + state snapshot for rollback/fine-tuning.

        Args:
            state: The graph state to checkpoint
            label: Label for this snapshot (e.g., "auto", "manual", "post_node")

        Returns:
            Dictionary with commit_sha, checkpoint_id, timestamp, and label
        """
        try:
            # Git snapshot of code
            timestamp = datetime.utcnow()
            confidence = state.get("confidence", 0)
            commit_msg = f"SNAPSHOT {label} - {timestamp} - Confidence {confidence}%"

            # Stage all backend files
            self.repo.index.add(["src/backend/"])

            # Check if there are changes to commit
            if self.repo.index.diff("HEAD"):
                commit = self.repo.index.commit(commit_msg)
                commit_sha = commit.hexsha
                logger.info(f"SnapshotEngine: Git snapshot created: {commit_sha}")
            else:
                commit_sha = self.repo.head.commit.hexsha
                logger.info(
                    f"SnapshotEngine: No changes to commit, using HEAD: {commit_sha}"
                )

            # LangGraph state checkpoint
            checkpoint = None
            if self.checkpointer:
                try:
                    thread_id = f"snapshot-{commit_sha}"
                    config = {"configurable": {"thread_id": thread_id}}
                    checkpoint = await self.checkpointer.aput(config, state)
                    logger.info(
                        f"SnapshotEngine: State checkpoint created: {checkpoint}"
                    )
                except Exception as e:
                    logger.warning(f"SnapshotEngine: Failed to create checkpoint: {e}")

            # Mem0 record
            if memory_loop:
                try:
                    await memory_loop.remember_node(state, f"snapshot_{label}")
                    logger.info(f"SnapshotEngine: Memory snapshot stored: {label}")
                except Exception as e:
                    logger.warning(
                        f"SnapshotEngine: Failed to store memory snapshot: {e}"
                    )

            return {
                "commit_sha": commit_sha,
                "checkpoint_id": checkpoint,
                "timestamp": timestamp.isoformat(),
                "label": label,
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"SnapshotEngine: Failed to take snapshot: {e}")
            return {
                "commit_sha": "unknown",
                "checkpoint_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "label": label,
                "error": str(e),
            }

    async def rollback_to_snapshot(self, commit_sha: str) -> dict[str, Any]:
        """
        Revert code to a previous snapshot state.

        Args:
            commit_sha: The git commit SHA to rollback to

        Returns:
            Dictionary with status and message
        """
        try:
            # Verify commit exists
            if commit_sha not in [c.hexsha[:10] for c in self.repo.iter_commits()]:
                # Try short SHA
                matching = [
                    c.hexsha
                    for c in self.repo.iter_commits()
                    if c.hexsha.startswith(commit_sha)
                ]
                if matching:
                    commit_sha = matching[0]
                else:
                    return {
                        "status": "error",
                        "message": f"Commit {commit_sha} not found",
                    }

            # Git checkout to the commit
            self.repo.git.checkout(commit_sha)
            logger.info(f"SnapshotEngine: Rolled back to commit {commit_sha}")

            return {
                "status": "success",
                "commit_sha": commit_sha,
                "message": f"Successfully rolled back to snapshot {commit_sha}",
            }

        except Exception as e:
            logger.error(f"SnapshotEngine: Rollback failed: {e}")
            return {"status": "error", "message": str(e)}

    async def list_snapshots(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        List recent snapshots.

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of snapshot info dictionaries
        """
        snapshots = []
        try:
            for commit in self.repo.iter_commits(max_count=limit):
                msg = commit.message
                if msg.startswith("SNAPSHOT"):
                    snapshots.append(
                        {
                            "commit_sha": commit.hexsha,
                            "short_sha": commit.hexsha[:10],
                            "message": msg.strip(),
                            "timestamp": commit.committed_datetime.isoformat(),
                        }
                    )
        except Exception as e:
            logger.error(f"SnapshotEngine: Failed to list snapshots: {e}")

        return snapshots


# Singleton instance
snapshot_engine = SnapshotEngine()

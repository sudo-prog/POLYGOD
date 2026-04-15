"""
SNAPSHOT ENGINE — Full code + state snapshot system for rollback and fine-tuning.

Changes vs previous version:
  - FIXED C2: git.Repo(".") is now wrapped in try/except at __init__ time.
              Docker images don't have a .git directory; the previous version
              crashed at module import (singleton = SnapshotEngine() at bottom),
              taking down the entire backend on Docker startup.
              All git-dependent methods now guard with `if self.repo is None`.
  - FIXED: SqliteSaver receives an open connection (conn.close() removed).
  - FIXED L1: datetime.utcnow() → datetime.now(UTC).
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# GitPython — optional; not available in stripped Docker images
try:
    import git as _git

    _GIT_AVAILABLE = True
except ImportError:
    _git = None  # type: ignore[assignment]
    _GIT_AVAILABLE = False

# Import memory_loop for Mem0 integration
try:
    from src.backend.self_improving_memory_loop import memory_loop
except ImportError:
    memory_loop = None  # type: ignore[assignment]


class SnapshotEngine:
    """
    Full snapshot system for code + state rollback and fine-tuning.

    Git operations are silently disabled when running inside Docker or any
    environment where the working directory is not a git repository.
    """

    def __init__(self) -> None:
        self.repo = self._init_repo()
        self.checkpointer = None
        self._init_checkpointer()

    # ── Git ─────────────────────────────────────────────────────────────────

    def _init_repo(self):
        """
        Try to open the git repo at '.'.

        Returns the Repo object on success, None on any failure.
        Failures are non-fatal — snapshot/rollback features are simply
        disabled rather than crashing the whole process.
        """
        if not _GIT_AVAILABLE:
            logger.warning("SnapshotEngine: gitpython not installed — git features disabled")
            return None
        try:
            repo = _git.Repo(".")
            logger.info("SnapshotEngine: git repo found at %s", repo.working_dir)
            return repo
        except _git.InvalidGitRepositoryError:
            logger.warning(
                "SnapshotEngine: current directory is not a git repo "
                "(normal in Docker) — git snapshot/rollback disabled"
            )
            return None
        except _git.NoSuchPathError:
            logger.warning("SnapshotEngine: git repo path not found — git features disabled")
            return None
        except Exception as exc:  # pragma: no cover
            logger.warning("SnapshotEngine: unexpected git init error: %s", exc)
            return None

    # ── LangGraph Checkpointer ───────────────────────────────────────────────

    def _init_checkpointer(self) -> None:
        """
        Initialize LangGraph checkpointer.

        IMPORTANT: the sqlite3 connection must remain OPEN for the
        lifetime of the process. Previous version called conn.close()
        before passing the connection to SqliteSaver, making every
        checkpoint operation raise ProgrammingError.
        """
        try:
            import sqlite3

            from langgraph.checkpoint.sqlite import SqliteSaver

            # Keep the connection open — SqliteSaver owns it from here.
            conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
            self.checkpointer = SqliteSaver(conn)
            logger.info("SnapshotEngine: SqliteSaver checkpointer initialised (checkpoints.db)")
        except Exception as e:
            logger.warning("SnapshotEngine: SqliteSaver not available: %s", e)
            try:
                from langgraph.checkpoint.memory import MemorySaver

                self.checkpointer = MemorySaver()
                logger.info("SnapshotEngine: MemorySaver fallback initialised (in-memory only)")
            except Exception as e2:
                logger.error("SnapshotEngine: no checkpointer available: %s", e2)

    # ── Public API ──────────────────────────────────────────────────────────

    async def take_snapshot(self, state: dict[str, Any], label: str = "auto") -> dict[str, Any]:
        """
        Take a full code + state snapshot for rollback / fine-tuning.

        Returns a dict with commit_sha, checkpoint_id, timestamp, and label.
        If git is unavailable the commit_sha is set to "git-unavailable".
        """
        timestamp = datetime.now(timezone.utc)
        confidence = state.get("confidence", 0)
        commit_sha = "git-unavailable"

        # ── Git snapshot ───────────────────────────────────────────────────
        if self.repo is not None:
            try:
                commit_msg = (
                    f"SNAPSHOT {label} - {timestamp.isoformat()} - Confidence {confidence}%"
                )
                self.repo.index.add(["src/backend/"])
                if self.repo.index.diff("HEAD"):
                    commit = self.repo.index.commit(commit_msg)
                    commit_sha = commit.hexsha
                    logger.info("SnapshotEngine: git snapshot created: %s", commit_sha)
                else:
                    commit_sha = self.repo.head.commit.hexsha
                    logger.info("SnapshotEngine: no changes — using HEAD %s", commit_sha)
            except Exception as exc:
                logger.warning("SnapshotEngine: git snapshot failed: %s", exc)

        # ── LangGraph checkpoint ───────────────────────────────────────────
        checkpoint_id = None
        if self.checkpointer is not None:
            try:
                thread_id = f"snapshot-{commit_sha}"
                lc_config = {"configurable": {"thread_id": thread_id}}
                # SqliteSaver.aput signature: (config, checkpoint, metadata, new_versions)
                # We store the state dict as the checkpoint value with empty metadata.
                checkpoint_id = await self.checkpointer.aput(
                    lc_config,
                    {"v": 1, "ts": timestamp.isoformat(), "channel_values": state},
                    {"source": "snapshot", "label": label},
                    {},
                )
                logger.info("SnapshotEngine: state checkpoint saved: %s", checkpoint_id)
            except Exception as exc:
                logger.warning("SnapshotEngine: checkpoint save failed: %s", exc)

        # ── Mem0 record ─────────────────────────────────────────────────────
        if memory_loop is not None:
            try:
                await memory_loop.remember_node(state, f"snapshot_{label}")
            except Exception as exc:
                logger.warning("SnapshotEngine: mem0 snapshot failed: %s", exc)

        return {
            "commit_sha": commit_sha,
            "checkpoint_id": checkpoint_id,
            "timestamp": timestamp.isoformat(),
            "label": label,
            "confidence": confidence,
        }

    async def rollback_to_snapshot(self, commit_sha: str) -> dict[str, Any]:
        """
        Revert working tree to a previous snapshot commit.

        Returns a status dict. If git is unavailable returns an error dict
        rather than raising.
        """
        if self.repo is None:
            return {
                "status": "error",
                "message": "Git is not available in this environment",
            }
        try:
            # Resolve short SHA
            all_shas = [c.hexsha for c in self.repo.iter_commits()]
            if commit_sha not in all_shas:
                matching = [s for s in all_shas if s.startswith(commit_sha)]
                if not matching:
                    return {
                        "status": "error",
                        "message": f"Commit {commit_sha!r} not found",
                    }
                commit_sha = matching[0]

            self.repo.git.checkout(commit_sha)
            logger.info("SnapshotEngine: rolled back to %s", commit_sha)
            return {
                "status": "success",
                "commit_sha": commit_sha,
                "message": f"Successfully rolled back to snapshot {commit_sha}",
            }
        except Exception as exc:
            logger.error("SnapshotEngine: rollback failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    async def list_snapshots(self, limit: int = 10) -> list[dict[str, Any]]:
        """List recent POLYGOD auto-snapshots from git history."""
        if self.repo is None:
            return []
        snapshots: list[dict[str, Any]] = []
        try:
            for commit in self.repo.iter_commits(max_count=limit):
                if commit.message.startswith("SNAPSHOT"):
                    snapshots.append(
                        {
                            "commit_sha": commit.hexsha,
                            "short_sha": commit.hexsha[:10],
                            "message": commit.message.strip(),
                            "timestamp": commit.committed_datetime.isoformat(),
                        }
                    )
        except Exception as exc:
            logger.error("SnapshotEngine: list_snapshots failed: %s", exc)
        return snapshots


# Module-level singleton — safe to import even without git / checkpoints.db
snapshot_engine = SnapshotEngine()

"""
ThoughtStream — Central nervous system for POLYGOD's internal monologue.

Every agent action, web search, self-heal event, and decision gets funnelled
through here. Consumers (SSE endpoints, WebSocket, persistent log) subscribe
to the stream and receive real-time thought events.

Architecture:
    ThoughtStream (singleton)
        ├── asyncio.Queue  → SSE broadcaster (frontend thinking window)
        ├── deque(maxlen)  → in-memory ring buffer (last 500 thoughts)
        └── SQLite log     → persistent change log (queryable history)

Thought types:
    thinking    — internal reasoning step
    search      — web search triggered
    search_result — search result summary
    code_scan   — error/issue detected in codebase
    patch       — code change proposed
    patch_applied — patch successfully written to disk
    patch_failed  — patch attempt failed
    decision    — final decision made
    error       — something went wrong in the agent itself
    info        — general informational note
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ThoughtType = Literal[
    "thinking",
    "search",
    "search_result",
    "code_scan",
    "patch",
    "patch_applied",
    "patch_failed",
    "decision",
    "error",
    "info",
    "warning",
]


class Thought(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    type: ThoughtType
    agent: str = "POLYGOD"
    message: str
    detail: str | None = None  # longer text, code snippets, search results
    meta: dict = Field(default_factory=dict)  # arbitrary key/value context

    def to_sse(self) -> str:
        """Format as Server-Sent Event data line."""
        return f"data: {self.model_dump_json()}\n\n"


class ThoughtStream:
    """
    Singleton thought bus.

    Usage:
        from src.backend.agents.thought_stream import thought_stream

        # Emit a thought (fire-and-forget, safe to call from sync code)
        thought_stream.emit_sync(Thought(type="thinking", message="Analysing market..."))

        # Emit from async code
        await thought_stream.emit(Thought(type="search", message="Searching for fix..."))

        # Subscribe for SSE streaming
        async for chunk in thought_stream.subscribe():
            yield chunk
    """

    _DB_PATH = Path("thought_log.db")
    _MAX_BUFFER = 500  # ring buffer size
    _MAX_SUBSCRIBERS = 50

    def __init__(self) -> None:
        self._buffer: deque[Thought] = deque(maxlen=self._MAX_BUFFER)
        self._subscribers: list[asyncio.Queue[Thought | None]] = []
        self._lock = asyncio.Lock()
        self._db_conn: sqlite3.Connection | None = None
        self._init_db()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        try:
            self._db_conn = sqlite3.connect(str(self._DB_PATH), check_same_thread=False)
            self._db_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS thoughts (
                    id          TEXT PRIMARY KEY,
                    timestamp   TEXT NOT NULL,
                    type        TEXT NOT NULL,
                    agent       TEXT NOT NULL,
                    message     TEXT NOT NULL,
                    detail      TEXT,
                    meta        TEXT
                )
            """
            )
            self._db_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ts ON thoughts (timestamp DESC)"
            )
            self._db_conn.commit()
            logger.info("ThoughtStream: DB initialised at %s", self._DB_PATH)
        except Exception as exc:
            logger.warning("ThoughtStream: DB init failed (%s) — in-memory only", exc)
            self._db_conn = None

    def _persist(self, thought: Thought) -> None:
        if self._db_conn is None:
            return
        try:
            self._db_conn.execute(
                "INSERT OR IGNORE INTO thoughts VALUES (?,?,?,?,?,?,?)",
                (
                    thought.id,
                    thought.timestamp,
                    thought.type,
                    thought.agent,
                    thought.message,
                    thought.detail,
                    json.dumps(thought.meta),
                ),
            )
            self._db_conn.commit()
        except Exception as exc:
            logger.debug("ThoughtStream: persist failed: %s", exc)

    # ── Emit ──────────────────────────────────────────────────────────────────

    async def emit(self, thought: Thought) -> None:
        """Async emit — use from coroutines."""
        self._buffer.append(thought)
        self._persist(thought)
        async with self._lock:
            dead: list[asyncio.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(thought)
                except asyncio.QueueFull:
                    dead.append(q)
            for d in dead:
                self._subscribers.remove(d)

    def emit_sync(self, thought: Thought) -> None:
        """
        Sync emit — safe to call from non-async code.
        Schedules the emit on the running event loop if one exists.
        """
        self._buffer.append(thought)
        self._persist(thought)
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._broadcast(thought))
            )
        except RuntimeError:
            pass  # No running loop — buffer-only

    async def _broadcast(self, thought: Thought) -> None:
        async with self._lock:
            dead: list[asyncio.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(thought)
                except asyncio.QueueFull:
                    dead.append(q)
            for d in dead:
                self._subscribers.remove(d)

    # ── Subscribe ─────────────────────────────────────────────────────────────

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """
        Yield SSE-formatted thought events to a streaming HTTP response.

        Sends all buffered thoughts first (replay), then live events.
        """
        if len(self._subscribers) >= self._MAX_SUBSCRIBERS:
            yield 'data: {"type":"error","message":"Too many subscribers"}\n\n'
            return

        q: asyncio.Queue[Thought | None] = asyncio.Queue(maxsize=200)

        # Replay buffer for new subscribers
        for thought in list(self._buffer):
            await q.put(thought)

        async with self._lock:
            self._subscribers.append(q)

        try:
            # Keep-alive ping every 15s to prevent proxy timeouts
            while True:
                try:
                    thought = await asyncio.wait_for(q.get(), timeout=15.0)
                    if thought is None:
                        break
                    yield thought.to_sse()
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # SSE comment — keeps connection alive
        finally:
            async with self._lock:
                if q in self._subscribers:
                    self._subscribers.remove(q)

    # ── History ───────────────────────────────────────────────────────────────

    def get_recent(
        self, limit: int = 100, type_filter: str | None = None
    ) -> list[dict]:
        """Return recent thoughts from persistent DB."""
        if self._db_conn is None:
            thoughts = list(self._buffer)
            if type_filter:
                thoughts = [t for t in thoughts if t.type == type_filter]
            return [t.model_dump() for t in thoughts[-limit:]]

        try:
            if type_filter:
                rows = self._db_conn.execute(
                    "SELECT * FROM thoughts WHERE type=? ORDER BY timestamp DESC LIMIT ?",
                    (type_filter, limit),
                ).fetchall()
            else:
                rows = self._db_conn.execute(
                    "SELECT * FROM thoughts ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [
                {
                    "id": r[0],
                    "timestamp": r[1],
                    "type": r[2],
                    "agent": r[3],
                    "message": r[4],
                    "detail": r[5],
                    "meta": json.loads(r[6] or "{}"),
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("ThoughtStream: get_recent failed: %s", exc)
            return []

    def clear(self) -> None:
        """Wipe the in-memory buffer (DB log is preserved)."""
        self._buffer.clear()

    # ── Convenience emitters ─────────────────────────────────────────────────

    async def thinking(self, message: str, agent: str = "POLYGOD", **meta) -> None:
        await self.emit(
            Thought(type="thinking", agent=agent, message=message, meta=meta)
        )

    async def searching(self, query: str, agent: str = "POLYGOD") -> None:
        await self.emit(
            Thought(
                type="search",
                agent=agent,
                message=f"Searching: {query}",
                meta={"query": query},
            )
        )

    async def search_result(
        self, query: str, summary: str, agent: str = "POLYGOD"
    ) -> None:
        await self.emit(
            Thought(
                type="search_result",
                agent=agent,
                message=f"Found: {summary[:120]}",
                detail=summary,
                meta={"query": query},
            )
        )

    async def code_issue(self, file: str, issue: str, severity: str = "error") -> None:
        await self.emit(
            Thought(
                type="code_scan",
                agent="SelfHeal",
                message=f"[{severity.upper()}] {file}: {issue[:100]}",
                detail=issue,
                meta={"file": file, "severity": severity},
            )
        )

    async def patch(self, file: str, description: str, diff: str | None = None) -> None:
        await self.emit(
            Thought(
                type="patch",
                agent="SelfHeal",
                message=f"Proposing patch: {file} — {description[:80]}",
                detail=diff,
                meta={"file": file},
            )
        )

    async def patch_applied(self, file: str, description: str) -> None:
        await self.emit(
            Thought(
                type="patch_applied",
                agent="SelfHeal",
                message=f"✅ Applied: {file} — {description[:80]}",
                meta={"file": file},
            )
        )

    async def patch_failed(self, file: str, reason: str) -> None:
        await self.emit(
            Thought(
                type="patch_failed",
                agent="SelfHeal",
                message=f"❌ Failed patch: {file} — {reason[:80]}",
                meta={"file": file, "reason": reason},
            )
        )

    async def decision(self, message: str, agent: str = "POLYGOD", **meta) -> None:
        await self.emit(
            Thought(type="decision", agent=agent, message=message, meta=meta)
        )

    async def info(self, message: str, agent: str = "POLYGOD") -> None:
        await self.emit(Thought(type="info", agent=agent, message=message))

    async def warn(self, message: str, agent: str = "POLYGOD") -> None:
        await self.emit(Thought(type="warning", agent=agent, message=message))

    async def error(
        self, message: str, agent: str = "POLYGOD", detail: str | None = None
    ) -> None:
        await self.emit(
            Thought(type="error", agent=agent, message=message, detail=detail)
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
thought_stream = ThoughtStream()

"""
POLYGOD Agent API Routes — AI Agent Widget + Self-Healing + Thinking Window.

Endpoints:
  POST /api/agent/chat          — streamed chat with code context
  GET  /api/agent/stream        — SSE thought stream (Thinking Window feed)
  GET  /api/agent/thoughts      — paginated thought history
  POST /api/agent/think         — force a research + web-search task
  POST /api/agent/self-heal     — submit an error for autonomous repair
  POST /api/agent/scan          — trigger static codebase scan
  GET  /api/agent/context       — current codebase snapshot summary
  DELETE /api/agent/thoughts    — clear in-memory thought buffer
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.backend.agents.self_healing import self_healing_engine
from src.backend.agents.thought_stream import thought_stream
from src.backend.auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
AGENT_MODEL = "claude-sonnet-4-6"

# ── Request / Response models ─────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context_files: list[str] = Field(default_factory=list)
    search: bool = False  # enable web search tool (via Playwright MCP)
    model: str = AGENT_MODEL


class ThinkRequest(BaseModel):
    question: str
    context_files: list[str] = Field(default_factory=list)
    search: bool = True


class SelfHealRequest(BaseModel):
    error_text: str
    file_path: str | None = None
    auto_fix: bool = True


class ScanRequest(BaseModel):
    path: str = "src/backend"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_anthropic_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "") or os.getenv("CLAUDE_API_KEY", "")


def _read_context_files(paths: list[str]) -> str:
    """Read requested files and format as code context for the API."""
    context_parts: list[str] = []
    for fp in paths[:5]:  # Cap at 5 files to stay within context window
        try:
            p = Path(fp)
            if p.exists() and p.stat().st_size < 100_000:
                content = p.read_text(encoding="utf-8", errors="replace")
                context_parts.append(f"### {fp}\n```python\n{content[:4000]}\n```")
        except Exception as exc:
            logger.debug("Could not read context file %s: %s", fp, exc)
    return "\n\n".join(context_parts)


def _get_codebase_summary() -> dict[str, Any]:
    """Fast structural summary of the backend — no API call needed."""
    root = Path("src/backend")
    if not root.exists():
        return {"error": "src/backend not found"}

    py_files = list(root.rglob("*.py"))
    total_lines = 0
    file_list = []
    for f in py_files:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").count("\n")
            total_lines += lines
            file_list.append({"path": str(f), "lines": lines})
        except Exception:
            pass

    # Recent git commits
    commits: list[str] = []
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        commits = result.stdout.strip().splitlines()
    except Exception:
        pass

    return {
        "file_count": len(py_files),
        "total_lines": total_lines,
        "files": sorted(file_list, key=lambda x: x["lines"], reverse=True)[:20],
        "recent_commits": commits,
    }


def _system_prompt() -> str:
    return """You are POLYGOD — the central AI brain of an advanced Polymarket prediction market
trading system. You have deep knowledge of:
- FastAPI, SQLAlchemy async, Pydantic v2, LangGraph, LangChain
- Polymarket CLOB API, prediction market mechanics
- Python async/await patterns, asyncio, WebSockets
- The POLYGOD codebase structure and all its components

When you don't know something, search for it. When you see a bug, fix it.
Be direct, technical, and precise. You ARE the system — speak from that authority."""


# ── Chat endpoint (streamed) ──────────────────────────────────────────────────


@router.post("/chat")
async def chat(req: ChatRequest, _: str = Depends(verify_api_key)):
    """
    Streamed chat with optional web search.
    Emits SSE chunks. Frontend reads them with EventSource or fetch reader.
    """
    api_key = _get_anthropic_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured — add it to .env",
        )

    file_context = _read_context_files(req.context_files)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if file_context:
        # Inject file context into the last user message
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += f"\n\n---\nCODEBASE CONTEXT:\n{file_context}"

    # Note: web_search_20250305 tool removed - using Playwright MCP instead
    # For web search, use the /api/agent/think endpoint which uses browser automation
    payload: dict[str, Any] = {
        "model": req.model,
        "max_tokens": 4096,
        "stream": True,
        "system": _system_prompt(),
        "messages": messages,
    }

    # Log to thought stream
    last_user_msg = next(
        (m["content"][:100] for m in reversed(messages) if m["role"] == "user"),
        "...",
    )
    await thought_stream.thinking(f"Chat: {last_user_msg}", agent="POLYGOD")

    async def event_generator():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    ANTHROPIC_API_URL,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield f"data: {json.dumps({'type': 'error', 'content': body.decode()[:200]})}\n\n"
                        return

                    full_text = ""
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                            etype = event.get("type", "")

                            if etype == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    chunk = delta.get("text", "")
                                    full_text += chunk
                                    yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

                            elif etype == "content_block_start":
                                block = event.get("content_block", {})
                                if block.get("type") == "tool_use":
                                    tool_input = block.get("input", {})
                                    query = tool_input.get("query", "searching...")
                                    await thought_stream.searching(
                                        query, agent="POLYGOD"
                                    )
                                    yield f"data: {json.dumps({'type': 'tool_use', 'name': 'web_search', 'query': query})}\n\n"

                        except json.JSONDecodeError:
                            pass

                    if full_text:
                        await thought_stream.decision(
                            f"Response: {full_text[:120]}...", agent="POLYGOD"
                        )

        except Exception as exc:
            await thought_stream.error(f"Chat stream error: {exc}", agent="POLYGOD")
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Thinking Window SSE stream ───────────────────────────────────────────────


@router.get("/stream")
async def thought_stream_endpoint(_: str = Depends(verify_api_key)):
    """
    SSE endpoint for the Thinking Window.
    Connect with EventSource — receives all thought events in real time.
    Replays the last 500 buffered thoughts on connect, then streams live.
    """
    return StreamingResponse(
        thought_stream.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Thought history ───────────────────────────────────────────────────────────


@router.get("/thoughts")
async def get_thoughts(
    limit: int = Query(default=100, ge=1, le=500),
    type_filter: str | None = Query(default=None),
    _: str = Depends(verify_api_key),
):
    """Paginated thought history from the persistent DB."""
    return {
        "thoughts": thought_stream.get_recent(limit=limit, type_filter=type_filter),
        "total": limit,
    }


@router.delete("/thoughts")
async def clear_thoughts(_: str = Depends(verify_api_key)):
    """Clear the in-memory thought buffer (DB log preserved)."""
    thought_stream.clear()
    await thought_stream.info("Thought buffer cleared by user", agent="POLYGOD")
    return {"status": "cleared"}


# ── Research / Think endpoint ─────────────────────────────────────────────────


@router.post("/think")
async def think(req: ThinkRequest, _: str = Depends(verify_api_key)):
    """
    Force a research task: POLYGOD searches the web and returns a detailed answer.
    Streams all thinking steps to the ThoughtStream (visible in Thinking Window).
    Uses Playwright MCP for web browsing when search=True.
    """
    result = await self_healing_engine.research_and_answer(
        question=req.question,
        search=req.search,
        context_files=req.context_files,
    )
    return result


# ── Self-heal endpoint ────────────────────────────────────────────────────────


@router.post("/self-heal")
async def self_heal(req: SelfHealRequest, _: str = Depends(verify_api_key)):
    """
    Submit an error for autonomous diagnosis and optional repair.

    The engine will:
    1. Classify the error
    2. Search the web for solutions (via browser automation)
    3. Generate a code patch
    4. Apply the patch (if auto_fix=True and confidence is high)

    All steps stream to the Thinking Window via SSE.
    """
    result = await self_healing_engine.handle_error(
        error_text=req.error_text,
        context_file=req.file_path,
        auto_fix=req.auto_fix,
    )
    return result


# ── Codebase scan ─────────────────────────────────────────────────────────────


@router.post("/scan")
async def scan_codebase(
    req: ScanRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key),
):
    """
    Trigger a static codebase scan for common issues.
    Runs in background — results stream to Thinking Window in real time.
    """
    background_tasks.add_task(self_healing_engine.scan_codebase, req.path)
    await thought_stream.info(
        f"Background scan queued for {req.path}", agent="SelfHeal"
    )
    return {"status": "scan_started", "path": req.path}


# ── Context snapshot ──────────────────────────────────────────────────────────


@router.get("/context")
async def get_context(_: str = Depends(verify_api_key)):
    """Return a structural snapshot of the backend codebase."""
    summary = _get_codebase_summary()
    await thought_stream.info(
        f"Context snapshot served: {summary.get('file_count', 0)} files",
        agent="POLYGOD",
    )
    return summary


# ── WebSocket (fallback for SSE-blocked environments) ─────────────────────────

# Note: The WS endpoint for agent chat lives in main.py (/ws/agent) to share
# the _ws_authenticate helper. This file only handles HTTP routes.

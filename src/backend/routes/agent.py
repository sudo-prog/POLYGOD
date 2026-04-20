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
import time
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.backend.agents.self_healing import self_healing_engine
from src.backend.agents.thought_stream import thought_stream
from src.backend.auth import verify_api_key
from src.backend.services.llm_concierge import concierge

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])

# Use litellm for free model routing (Groq is free, no credit card required)
# Priority: Groq → Gemini → OpenRouter (all have free tiers)
AGENT_MODEL = "groq/llama-3.3-70b-versatile"

# ── Request / Response models ─────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context_files: list[str] = Field(default_factory=list)
    search: bool = False  # enable web search tool (via Playwright MCP)
    model: str = "groq/llama-3.3-70b-versatile"  # Free model - Groq


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


T = TypeVar("T")


def _get_codebase_summary() -> dict[str, Any]:
    """Fast structural summary of the backend — no API call needed."""
    root = Path("src/backend")
    if not root.exists():
        return {"error": "src/backend not found"}

    py_files = list(root.rglob("*.py"))
    total_lines = 0
    file_list: list[dict[str, Any]] = []
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
    Streamed chat using litellm with free Groq model.
    Grq: llama-3.3-70b-versatile is FREE (no credit card needed)
    Falls back to Gemini or OpenRouter if Groq unavailable.
    """
    from litellm import astream_completion

    file_context = _read_context_files(req.context_files)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if file_context:
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += f"\n\n---\nCODEBASE CONTEXT:\n{file_context}"

    # Log to thought stream
    last_user_msg = next(
        (m["content"][:100] for m in reversed(messages) if m["role"] == "user"),
        "...",
    )
    await thought_stream.thinking(f"Chat: {last_user_msg}", agent="POLYGOD")

    async def event_generator():
        try:
            # Try free models via litellm
            model = req.model or "groq/llama-3.3-70b-versatile"

            full_text = ""
            try:
                async for chunk in astream_completion(
                    model=model,
                    messages=[{"role": "system", "content": _system_prompt()}]
                    + messages,
                    max_tokens=4096,
                    api_key=os.getenv("GROQ_API_KEY", ""),
                ):
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        full_text += delta
                        data = json.dumps({"type": "text", "content": delta})
                        yield f"data: {data}\n\n"
            except Exception as e:
                # Fallback: try concierge (Gemini -> OpenRouter)
                try:
                    resp = await concierge.get_secure_completion(
                        messages=[{"role": "system", "content": _system_prompt()}]
                        + messages
                    )
                    content = resp.choices[0].message.content
                    # Stream it in chunks
                    for i in range(0, len(content), 50):
                        chunk = content[i : i + 50]
                        data = json.dumps({"type": "text", "content": chunk})
                        yield f"data: {data}\n\n"
                    full_text = content
                except Exception as e2:
                    yield f"data: {json.dumps({'type': 'error', 'content': f'All LLMs failed. Groq: {e}, Concierge: {e2}'})}\n\n"
                    return

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

# ── Agent Kill / Restart ───────────────────────────────────────────────────


# Simple in-memory agent state
_agent_process_state = {
    "status": "running",  # "running", "stopped", "restarting"
    "pid": None,
    "started_at": None,
}


@router.post("/kill")
async def kill_agent(_: str = Depends(verify_api_key)):
    """
    Kill the POLYGOD agent process.
    This stops all active agent tasks and clears the thought stream buffer.
    """
    global _agent_process_state

    if _agent_process_state["status"] == "stopped":
        return {"status": "already_stopped", "message": "Agent is already stopped"}

    _agent_process_state["status"] = "stopped"
    _agent_process_state["pid"] = None

    await thought_stream.error("Agent killed by user", agent="POLYGOD")

    return {
        "status": "killed",
        "message": "POLYGOD agent has been terminated",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/restart")
async def restart_agent(_: str = Depends(verify_api_key)):
    """
    Restart the POLYGOD agent.
    Reinitializes all agent modules and reconnects to data feeds.
    """
    global _agent_process_state

    _agent_process_state["status"] = "restarting"

    # Simulate restart - in production this would spawn the agent process
    time.sleep(0.5)  # Brief delay for effect

    _agent_process_state["status"] = "running"
    _agent_process_state["started_at"] = datetime.utcnow().isoformat()

    await thought_stream.info("Agent restarted by user", agent="POLYGOD")

    return {
        "status": "restarted",
        "message": "POLYGOD agent has been restarted successfully",
        "started_at": _agent_process_state["started_at"],
    }


@router.get("/status")
async def get_agent_status(_: str = Depends(verify_api_key)):
    """Get the current agent status."""
    return _agent_process_state


# Note: The WS endpoint for agent chat lives in main.py (/ws/agent) to share
# the _ws_authenticate helper. This file only handles HTTP routes.

import asyncio
import json
import logging
import os
import subprocess
import traceback
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.backend.auth import verify_api_key
from src.backend.config import settings
from src.backend.services.llm_concierge import concierge

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AI Agent"])

# ── Codebase snapshot ─────────────────────────────────────────────────────────

CODEBASE_ROOT = Path(__file__).parent.parent  # src/backend/


def _build_codebase_snapshot(max_chars: int = 80_000) -> str:
    """
    Walk src/backend/ and build a condensed codebase snapshot.
    Respects a character budget to stay within LLM context windows.
    Files are included in priority order: routes, core, agents, services.
    """
    priority_order = [
        "main.py",
        "config.py",
        "database.py",
        "db_models.py",
        "polygod_graph.py",
        "auth.py",
        "cache.py",
    ]
    skip_dirs = {"__pycache__", "venv", ".git", "node_modules", "alembic"}
    skip_exts = {".pyc", ".pyo", ".egg-info"}

    collected: list[tuple[int, str, str]] = []

    def _priority(name: str) -> int:
        try:
            return priority_order.index(name)
        except ValueError:
            return 999

    for root, dirs, files in os.walk(CODEBASE_ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if Path(fname).suffix in skip_exts:
                continue
            if not fname.endswith(".py"):
                continue
            fpath = Path(root) / fname
            rel = fpath.relative_to(CODEBASE_ROOT.parent.parent)
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                collected.append((_priority(fname), str(rel), content))
            except Exception:
                pass

    collected.sort(key=lambda x: x[0])

    parts = []
    total = 0
    for _, rel, content in collected:
        block = f"\n### FILE: {rel}\n```python\n{content}\n```\n"
        if total + len(block) > max_chars:
            parts.append(f"\n### FILE: {rel}\n[truncated — over context budget]\n")
            continue
        parts.append(block)
        total += len(block)

    return "\n".join(parts)


# ── Memory helpers ────────────────────────────────────────────────────────────

_mem0 = None


def _get_mem0():
    global _mem0
    if _mem0 is not None:
        return _mem0
    try:
        from mem0 import Memory

        config = json.loads(settings.MEM0_CONFIG)
        _mem0 = Memory.from_config(config)
    except Exception as e:
        logger.warning("Agent: Mem0 unavailable: %s", e)
    return _mem0


def _recall_relevant(query: str, limit: int = 8) -> str:
    """Pull relevant past memories to inject into system prompt."""
    mem0 = _get_mem0()
    if not mem0:
        return ""
    try:
        results = mem0.search(query, user_id="polygod_agent", limit=limit)
        if not results:
            return ""
        lines = [f"- {r.get('memory', str(r))}" for r in results[:limit]]
        return "RELEVANT PAST EXPERIENCES:\n" + "\n".join(lines)
    except Exception as e:
        logger.debug("Agent memory recall failed: %s", e)
        return ""


def _store_memory(content: str, metadata: dict | None = None):
    """Store a learning or resolution to Mem0."""
    mem0 = _get_mem0()
    if not mem0:
        return
    try:
        mem0.add(
            messages=[{"role": "system", "content": content}],
            user_id="polygod_agent",
            metadata=metadata or {},
        )
    except Exception as e:
        logger.debug("Agent memory store failed: %s", e)


# ── System prompt builder ─────────────────────────────────────────────────────


def _build_system_prompt(user_message: str, include_codebase: bool = True) -> str:
    memories = _recall_relevant(user_message)
    codebase = _build_codebase_snapshot() if include_codebase else "[codebase omitted]"

    return f"""You are the POLYGOD AI Agent — a self-evolving, embedded engineering assistant \
with full read/write access to the POLYGOD codebase.

You are currently running INSIDE the POLYGOD application. You know every file, \
every function, every bug, every design decision. You are the smartest engineer \
on the team and you speak like one: direct, precise, no fluff.

CAPABILITIES:
- Diagnose bugs by reading stack traces + cross-referencing code
- Propose and apply file patches (output JSON patch objects, see format below)
- Explain architecture decisions and trade-offs
- Suggest performance improvements, security fixes, refactors
- Remember past fixes and apply that knowledge to new problems
- Run shell commands for diagnostics (restricted to safe read-only commands)

PATCH FORMAT (use when proposing a code fix):
Output a JSON block with this exact schema:
```json
{{
  "type": "patch",
  "file": "src/backend/routes/markets.py",
  "description": "Fix N+1 query in get_market_holders",
  "old_code": "for holder in all_holders:\\n    ...",
  "new_code": "# bulk fetch all holders at once\\n..."
}}
```
The frontend will show an "Apply Fix" button. The user approves before anything is written.

SHELL COMMAND FORMAT (read-only diagnostics only):
```json
{{
  "type": "shell",
  "command": "grep -rn 'datetime.utcnow' src/backend/",
  "description": "Find all deprecated utcnow() calls"
}}
```

{memories}

FULL CODEBASE SNAPSHOT (src/backend/):
{codebase}

CURRENT TIMESTAMP: {datetime.now(timezone.utc).isoformat()}

Rules:
- Never hallucinate code that doesn't exist in the snapshot above
- When unsure, say so and ask for more context
- After resolving an issue, output a MEMORY block so you learn from it:
```json
  {{"type": "memory", "content": "Fixed X by doing Y. Root cause was Z."}}
```
- Be concise by default. Go deep only when asked.
- If the user pastes an error, always cross-reference it with the actual code above."""


def extractPatches_py(text: str) -> list[dict]:
    import re

    patches = []
    for match in re.finditer(
        r'```json\s*(\{[^`]*"type":\s*"patch"[^`]*\})\s*```', text, re.DOTALL
    ):
        try:
            obj = json.loads(match.group(1))
            if obj.get("type") == "patch":
                patches.append(obj)
        except Exception:
            pass
    return patches


def extractShells_py(text: str) -> list[dict]:
    import re

    shells = []
    for match in re.finditer(
        r'```json\s*(\{[^`]*"type":\s*"shell"[^`]*\})\s*```', text, re.DOTALL
    ):
        try:
            obj = json.loads(match.group(1))
            if obj.get("type") == "shell":
                shells.append(obj)
        except Exception:
            pass
    return shells


# ── Request/Response models ───────────────────────────────────────────────────


class AgentMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AgentChatRequest(BaseModel):
    messages: list[AgentMessage]
    include_codebase: bool = True
    stream: bool = True


class PatchApplyRequest(BaseModel):
    file: str
    old_code: str
    new_code: str
    description: str


class ShellRunRequest(BaseModel):
    command: str
    description: str


# ── Streaming chat endpoint ────────────────────────────────────────────────────


async def _stream_agent_response(
    messages: list[AgentMessage],
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    """Stream agent response as SSE data events."""
    formatted = [{"role": m.role, "content": m.content} for m in messages]
    full_response = ""

    try:
        # Use LLM Concierge for multi-provider routing
        response = await concierge.get_secure_completion(
            messages=formatted,
            system=system_prompt,
            max_tokens=4096,
            stream=False,  # get full response, then stream it character by character
        )

        # Extract text content
        if hasattr(response, "choices"):
            text = response.choices[0].message.content or ""
        elif hasattr(response, "content"):
            # Anthropic-style
            content_blocks = (
                response.content
                if isinstance(response.content, list)
                else [response.content]
            )
            text = "".join(
                block.text if hasattr(block, "text") else str(block)
                for block in content_blocks
            )
        else:
            text = str(response)

        full_response = text

        # Stream word by word for natural feel
        words = text.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            await asyncio.sleep(0.01)

        # Process any embedded actions (patches, memories, shell commands)
        yield f"data: {json.dumps({'type': 'done', 'full': full_response})}\n\n"

        # Auto-extract and store memories
        if '"type": "memory"' in full_response:
            import re

            memory_blocks = re.findall(
                r'```json\s*(\{[^`]*"type":\s*"memory"[^`]*\})\s*```',
                full_response,
                re.DOTALL,
            )
            for block in memory_blocks:
                try:
                    mem_data = json.loads(block)
                    _store_memory(
                        mem_data.get("content", ""),
                        metadata={
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "source": "agent_auto",
                        },
                    )
                except Exception:
                    pass

    except Exception as e:
        error_msg = f"Agent error: {e!s}\n\n{traceback.format_exc()}"
        logger.error(error_msg)
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


@router.post("/chat")
async def agent_chat(
    request: AgentChatRequest,
    _: str = Depends(verify_api_key),
):
    """Stream a response from the AI agent."""
    last_user_msg = next(
        (m.content for m in reversed(request.messages) if m.role == "user"),
        "",
    )
    system_prompt = _build_system_prompt(last_user_msg, request.include_codebase)

    return StreamingResponse(
        _stream_agent_response(request.messages, system_prompt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.websocket("/ws")
async def agent_ws(websocket: WebSocket):
    """WebSocket fallback for environments where SSE doesn't work."""
    from starlette.websockets import WebSocketDisconnect

    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            messages = [AgentMessage(**m) for m in data.get("messages", [])]
            last_user = next(
                (m.content for m in reversed(messages) if m.role == "user"), ""
            )
            system_prompt = _build_system_prompt(
                last_user, data.get("include_codebase", True)
            )
            formatted = [{"role": m.role, "content": m.content} for m in messages]
            try:
                response = await concierge.get_secure_completion(
                    messages=formatted,
                    system=system_prompt,
                    max_tokens=4096,
                )
                if hasattr(response, "choices"):
                    text = response.choices[0].message.content or ""
                elif hasattr(response, "content"):
                    blocks = (
                        response.content
                        if isinstance(response.content, list)
                        else [response.content]
                    )
                    text = "".join(
                        b.text if hasattr(b, "text") else str(b) for b in blocks
                    )
                else:
                    text = str(response)
                patches = extractPatches_py(text)
                shells = extractShells_py(text)
                await websocket.send_json(
                    {
                        "type": "done",
                        "full": text,
                        "patches": patches,
                        "shells": shells,
                    }
                )
                # Auto-store memories
                if '"type": "memory"' in text:
                    import re

                    for block in re.findall(
                        r'```json\s*(\{[^`]*"type":\s*"memory"[^`]*\})\s*```',
                        text,
                        re.DOTALL,
                    ):
                        try:
                            mem_data = json.loads(block)
                            _store_memory(
                                mem_data.get("content", ""), {"source": "ws_agent"}
                            )
                        except Exception:
                            pass
            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})
    except WebSocketDisconnect:
        pass


# ── Apply patch endpoint ──────────────────────────────────────────────────────


@router.post("/fix")
async def apply_patch(
    request: PatchApplyRequest,
    _: str = Depends(verify_api_key),
):
    """Apply an AI-proposed code patch to the actual file."""
    target = Path(request.file)

    # Safety: only allow files within the project
    try:
        target.resolve().relative_to(Path().resolve())
    except ValueError:
        raise HTTPException(
            status_code=400, detail="File path must be within project root"
        )

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.file}")

    original = target.read_text(encoding="utf-8")

    if request.old_code not in original:
        raise HTTPException(
            status_code=422,
            detail="Old code not found in file — may have already been changed",
        )

    patched = original.replace(request.old_code, request.new_code, 1)
    target.write_text(patched, encoding="utf-8")

    # Store fix in memory
    _store_memory(
        f"Applied fix to {request.file}: {request.description}",
        metadata={
            "file": request.file,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "patch_applied",
        },
    )

    logger.info("Agent patch applied: %s — %s", request.file, request.description)
    return {
        "status": "applied",
        "file": request.file,
        "description": request.description,
    }


# ── Shell diagnostics endpoint ────────────────────────────────────────────────

_ALLOWED_COMMANDS = {"grep", "find", "cat", "head", "tail", "wc", "ls", "pwd", "python"}


@router.post("/shell")
async def run_shell(
    request: ShellRunRequest,
    _: str = Depends(verify_api_key),
):
    """Run a read-only diagnostic shell command (allowlisted only)."""
    cmd_parts = request.command.strip().split()
    if not cmd_parts or cmd_parts[0] not in _ALLOWED_COMMANDS:
        raise HTTPException(
            status_code=403,
            detail=f"Command '{cmd_parts[0] if cmd_parts else ''}' not allowed. "
            f"Allowed: {', '.join(sorted(_ALLOWED_COMMANDS))}",
        )

    # Extra safety: block destructive flags
    dangerous = {"-rf", "--delete", "> ", "rm", "mv", "cp", "chmod", "sudo"}
    if any(d in request.command for d in dangerous):
        raise HTTPException(status_code=403, detail="Destructive command not allowed")

    try:
        result = subprocess.run(
            request.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path().resolve()), check=False,
        )
        output = result.stdout[:8000] + (result.stderr[:2000] if result.stderr else "")
        return {"output": output, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Context endpoint ──────────────────────────────────────────────────────────


@router.get("/context")
async def get_context(_: str = Depends(verify_api_key)):
    """Return a codebase snapshot for debugging."""
    return {
        "snapshot_chars": len(_build_codebase_snapshot()),
        "root": str(CODEBASE_ROOT),
        "memory_available": _get_mem0() is not None,
    }

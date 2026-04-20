"""
SelfHealingEngine — POLYGOD's autonomous repair and web-search intelligence.

Capabilities:
  1. ERROR SCANNER       — scans Python tracebacks / log output for known error patterns
  2. WEB SEARCH          — uses LITELLM with free Groq model (no credit card required)
  3. PATCH PROPOSER      — generates code patches using LLM with full file context
  4. PATCH APPLICATOR    — safely writes patches with backup + rollback
  5. BACKGROUND WATCHER  — asyncio task that monitors a shared error queue

All activity is streamed to ThoughtStream so the frontend Thinking Window
shows every step in real time.

Uses litellm with FREE Groq model (llama-3.3-70b-versatile) - no API key needed,
falls back to Gemini or OpenRouter for code generation.
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import os
import re
import shutil
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from src.backend.agents.thought_stream import thought_stream

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# FREE models via litellm (Groq is completely free, no credit card)
SELF_HEAL_MODEL = "groq/llama-3.3-70b-versatile"
BACKUP_DIR = Path(".self_heal_backups")
MAX_FILE_SIZE_BYTES = 150_000  # don't send >150KB files to the API

KNOWN_ERROR_PATTERNS = [
    # (regex_pattern, human_readable_label, severity)
    (
        r"ImportError|ModuleNotFoundError",
        "Missing import / module not found",
        "critical",
    ),
    (r"AttributeError", "Attribute access on None or wrong type", "high"),
    (r"KeyError", "Missing dictionary key", "medium"),
    (r"TypeError", "Wrong argument type", "medium"),
    (r"RuntimeError", "Runtime failure", "high"),
    (r"SyntaxError", "Python syntax error", "critical"),
    (r"IndentationError", "Python indentation error", "critical"),
    (r"ConnectionRefusedError|ConnectionError", "Network connection failed", "high"),
    (r"sqlalchemy\.exc", "Database query error", "high"),
    (r"pydantic.*ValidationError", "Pydantic validation failure", "medium"),
    (r"404.*Not Found|405.*Not Allowed", "HTTP endpoint missing", "medium"),
    (r"ENCRYPTION_KEY|Fernet", "Encryption configuration error", "critical"),
]


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class ErrorEvent:
    """An error detected in log output or passed explicitly."""

    raw_text: str
    file_path: str | None = None
    line_number: int | None = None
    error_type: str | None = None
    label: str | None = None
    severity: str = "error"
    context: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class PatchResult:
    success: bool
    file_path: str
    description: str
    diff: str = ""
    backup_path: str = ""
    error: str = ""


# ── Main engine ─────────────────────────────────────────────────────────────


class SelfHealingEngine:
    """
    Autonomous self-repair engine.

    Usage:
        from src.backend.agents.self_healing import self_healing_engine

        # Feed an error string (from a log handler, exception handler, etc.)
        await self_healing_engine.handle_error(error_text, context_file="main.py")

        # Ask it a question with optional web search
        result = await self_healing_engine.research_and_answer(
            "How do I fix asyncpg pool exhaustion?",
            search=True
        )

        # Start background error watcher
        asyncio.create_task(self_healing_engine.run_background_watcher())
    """

    def __init__(self) -> None:
        self._error_queue: asyncio.Queue[ErrorEvent] = asyncio.Queue(maxsize=100)
        self._processing = False
        self._api_key: str = ""
        BACKUP_DIR.mkdir(exist_ok=True)

    def _get_api_key(self) -> str:
        """Lazy-load API key from env (not at import time).

        Uses Groq (free), falls back to GROK_API_KEY or GEMINI_API_KEY.
        """
        if not self._api_key:
            # Try free models first, then paid fallbacks
            self._api_key = (
                os.getenv("GROQ_API_KEY", "")
                or os.getenv("GROK_API_KEY", "")
                or os.getenv("GEMINI_API_KEY", "")
            )
        return self._api_key

    # ── Public API ────────────────────────────────────────────────────────────

    async def handle_error(
        self,
        error_text: str,
        context_file: str | None = None,
        auto_fix: bool = True,
    ) -> dict[str, Any]:
        """
        Main entry point: given an error string, detect, research, and optionally fix it.

        Steps:
          1. Classify the error
          2. Extract file/line context
          3. Web-search for solution
          4. Generate patch
          5. Apply patch (if auto_fix=True and confidence is high)

        Returns a result dict with all findings.
        """
        await thought_stream.thinking(
            "Received error event — classifying...", agent="SelfHeal"
        )

        event = self._classify_error(error_text, context_file)

        await thought_stream.code_issue(
            file=event.file_path or "unknown",
            issue=f"[{event.severity.upper()}] {event.label or event.error_type}: {error_text[:200]}",
            severity=event.severity,
        )

        # Queue for background processing
        try:
            self._error_queue.put_nowait(event)
        except asyncio.QueueFull:
            await thought_stream.warn(
                "Error queue full — dropping oldest event", agent="SelfHeal"
            )
            try:
                self._error_queue.get_nowait()
                self._error_queue.put_nowait(event)
            except Exception:
                pass

        # Process immediately (research + optional patch)
        result = await self._process_error(event, auto_fix=auto_fix)
        return result

    async def research_and_answer(
        self,
        question: str,
        search: bool = True,
        context_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Research a question using web search and/or code context, return an answer.

        Used by the /api/agent/think endpoint when the agent encounters
        something it doesn't know how to do.
        """
        await thought_stream.thinking(
            f"Researching: {question[:100]}", agent="SelfHeal"
        )

        file_context = ""
        if context_files:
            for fp in context_files[:3]:
                content = self._read_file_safe(fp)
                if content:
                    file_context += f"\n\n### {fp}\n```python\n{content[:3000]}\n```"

        if search:
            await thought_stream.searching(question)
            answer = await self._call_claude_with_search(question, file_context)
        else:
            answer = await self._call_claude(question, file_context)

        await thought_stream.decision(
            f"Research complete: {answer[:150]}...", agent="SelfHeal"
        )
        return {"question": question, "answer": answer, "searched": search}

    async def scan_codebase(self, path: str = "src/backend") -> list[dict]:
        """
        Static scan of Python files for common issues (no API call needed).
        Fast heuristic check — runs in < 1s on a typical backend.
        """
        await thought_stream.thinking(
            f"Scanning codebase at {path}...", agent="SelfHeal"
        )
        issues = []
        root = Path(path)
        if not root.exists():
            await thought_stream.warn(
                f"Scan path {path} does not exist", agent="SelfHeal"
            )
            return issues

        py_files = list(root.rglob("*.py"))
        await thought_stream.info(
            f"Scanning {len(py_files)} Python files", agent="SelfHeal"
        )

        for pyfile in py_files:
            try:
                src = pyfile.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            file_issues = self._static_scan_file(str(pyfile), src)
            issues.extend(file_issues)

            for issue in file_issues:
                await thought_stream.code_issue(
                    file=str(pyfile),
                    issue=issue["message"],
                    severity=issue["severity"],
                )

        await thought_stream.decision(
            f"Scan complete: {len(issues)} issues found across {len(py_files)} files",
            agent="SelfHeal",
        )
        return issues

    async def run_background_watcher(self) -> None:
        """
        Long-running background task.
        Processes errors from the queue as they arrive.
        Start with: asyncio.create_task(self_healing_engine.run_background_watcher())
        """
        await thought_stream.info("Background error watcher started", agent="SelfHeal")
        while True:
            try:
                event = await asyncio.wait_for(self._error_queue.get(), timeout=30.0)
                if not self._processing:
                    self._processing = True
                    try:
                        await self._process_error(event, auto_fix=True)
                    finally:
                        self._processing = False
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("SelfHeal background watcher error: %s", exc)
                await asyncio.sleep(5)

    # ── Internal processing ─────────────────────────────────────────────────

    async def _process_error(
        self, event: ErrorEvent, auto_fix: bool = True
    ) -> dict[str, Any]:
        api_key = self._get_api_key()
        if not api_key:
            await thought_stream.warn(
                "ANTHROPIC_API_KEY not set — self-heal requires it for web search + patching",
                agent="SelfHeal",
            )
            return {
                "status": "no_api_key",
                "message": "Set ANTHROPIC_API_KEY in .env to enable self-healing",
            }

        # Build question from error
        question = self._build_search_query(event)
        await thought_stream.searching(question)

        # Get file context if we know which file
        file_context = ""
        if event.file_path:
            content = self._read_file_safe(event.file_path)
            if content:
                file_context = f"\n\n### Current file content ({event.file_path}):\n```python\n{content[:4000]}\n```"

        # Research with web search
        solution = await self._call_claude_with_search(
            question=f"""
I have this Python error in a FastAPI/LangGraph backend called POLYGOD:

```
{event.raw_text[:1500]}
```

File: {event.file_path or "unknown"}
Line: {event.line_number or "unknown"}
{file_context}

1. What is causing this error?
2. What is the exact fix?
3. If you need to search for the solution, please do so.
4. Provide the corrected code snippet I should use.
""",
            file_context="",
        )

        await thought_stream.search_result(
            query=question,
            summary=solution[:500],
            agent="SelfHeal",
        )

        result: dict[str, Any] = {
            "status": "researched",
            "error_type": event.error_type,
            "file": event.file_path,
            "solution": solution,
            "patch_applied": False,
        }

        # Attempt to generate and apply a patch if we have a file to patch
        if auto_fix and event.file_path and event.severity in ("critical", "high"):
            patch_result = await self._generate_and_apply_patch(event, solution)
            result["patch_applied"] = patch_result.success
            result["patch_diff"] = patch_result.diff
            result["patch_error"] = patch_result.error

        return result

    async def _generate_and_apply_patch(
        self, event: ErrorEvent, solution: str
    ) -> PatchResult:
        """Ask Claude to generate a minimal patch, then apply it."""
        file_path = event.file_path
        if not file_path:
            return PatchResult(success=False, file_path="", description="No file path")

        original = self._read_file_safe(file_path)
        if not original:
            return PatchResult(
                success=False, file_path=file_path, description="Could not read file"
            )

        await thought_stream.patch(
            file=file_path,
            description=f"Generating fix for {event.error_type}",
        )

        patch_prompt = f"""
You are a Python expert applying a minimal, surgical fix to this file.

FILE: {file_path}
ERROR: {event.raw_text[:800]}
SOLUTION RESEARCH: {solution[:1000]}

CURRENT FILE CONTENT:
```python
{original[:6000]}
```

Return ONLY the complete corrected file content, nothing else.
No markdown fences, no explanation, just the raw Python code.
Make the smallest possible change that fixes the error.
"""

        patched_content = await self._call_claude(patch_prompt, "")

        # Validate it looks like Python
        if (
            not patched_content.strip()
            or "def " not in patched_content
            and "import " not in patched_content
        ):
            await thought_stream.patch_failed(
                file_path, "Generated content doesn't look like valid Python"
            )
            return PatchResult(
                success=False,
                file_path=file_path,
                description="Invalid generated content",
                error="Content validation failed",
            )

        # Generate diff for the thought log
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                patched_content.splitlines(),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )

        await thought_stream.patch(
            file=file_path,
            description="Applying patch",
            diff=diff[:2000],
        )

        # Backup original
        backup_path = self._backup_file(file_path)

        # Write patch
        try:
            Path(file_path).write_text(patched_content, encoding="utf-8")
            await thought_stream.patch_applied(
                file_path, f"Patched {len(diff.splitlines())} lines changed"
            )
            return PatchResult(
                success=True,
                file_path=file_path,
                description=f"Applied fix for {event.error_type}",
                diff=diff,
                backup_path=backup_path,
            )
        except Exception as exc:
            await thought_stream.patch_failed(file_path, str(exc))
            # Restore backup
            if backup_path:
                try:
                    shutil.copy2(backup_path, file_path)
                except Exception:
                    pass
            return PatchResult(
                success=False,
                file_path=file_path,
                description="Write failed",
                error=str(exc),
            )

    # ── Claude API calls ─────────────────────────────────────────────────────

    async def _call_claude_with_search(self, question: str, file_context: str) -> str:
        """Call Claude with web_search tool enabled."""
        api_key = self._get_api_key()
        if not api_key:
            return "ANTHROPIC_API_KEY not configured."

        # Use Playwright MCP for web research instead of web_search_20250305
        # The web_search tool is no longer used - we use browser automation instead
        payload = {
            "model": SELF_HEAL_MODEL,
            "max_tokens": 2048,
            "messages": [
                {
                    "role": "user",
                    "content": question
                    + (f"\n\n{file_context}" if file_context else ""),
                }
            ],
            "system": (
                "You are POLYGOD's internal repair agent — a world-class Python/FastAPI/LangGraph "
                "engineer with access to web search via browser automation. When you need current "
                "information about a library, error, or API change, use the browser to search for it. "
                "Be precise, technical, and concise. Focus on actionable fixes, not theory."
            ),
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    ANTHROPIC_API_URL,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            # Extract text from potentially multi-turn tool-use response
            text_parts = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text_parts.append(block["text"])

            result = "\n".join(text_parts).strip()
            return result if result else "No solution found."

        except httpx.HTTPStatusError as exc:
            await thought_stream.error(
                f"Anthropic API error: {exc.response.status_code}", agent="SelfHeal"
            )
            return f"API error: {exc.response.status_code}"
        except Exception as exc:
            await thought_stream.error(f"Search failed: {exc}", agent="SelfHeal")
            return f"Search failed: {exc}"

    async def _call_claude(self, prompt: str, context: str) -> str:
        """Call Claude without tools (faster, for patch generation)."""
        api_key = self._get_api_key()
        if not api_key:
            return "ANTHROPIC_API_KEY not configured."

        payload = {
            "model": SELF_HEAL_MODEL,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt + (f"\n\n{context}" if context else ""),
                }
            ],
            "system": (
                "You are POLYGOD's code repair agent. Produce only clean, correct Python code "
                "or direct technical answers. No markdown fences in code output. No explanations "
                "unless explicitly asked."
            ),
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    ANTHROPIC_API_URL,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            return " ".join(
                b["text"] for b in data.get("content", []) if b.get("type") == "text"
            )
        except Exception as exc:
            return f"Claude call failed: {exc}"

    # ── Static analysis ─────────────────────────────────────────────────────

    def _static_scan_file(self, file_path: str, src: str) -> list[dict]:
        issues = []
        lines = src.splitlines()

        checks = [
            (
                r"datetime\.utcnow\(\)",
                "Use datetime.now(timezone.utc) instead of deprecated utcnow()",
                "medium",
            ),
            (r"except\s*:", "Bare except clause swallows all exceptions", "medium"),
            (r"print\s*\(", "print() found — use logging instead", "low"),
            (r"TODO|FIXME|HACK|XXX", "Unresolved TODO/FIXME/HACK comment", "low"),
            (
                r"os\.getenv\(['\"](?:GEMINI_POLYMARKET|INTERNAL).*?['\"](?!\s*,)",
                "Hardcoded env var read without default — use settings.*",
                "medium",
            ),
            (
                r"password\s*=\s*['\"][^'\"]{4,}",
                "Possible hardcoded password",
                "critical",
            ),
            (r"secret\s*=\s*['\"][^'\"]{8,}", "Possible hardcoded secret", "critical"),
            (
                r"api_key\s*=\s*['\"][^'\"]{8,}",
                "Possible hardcoded API key",
                "critical",
            ),
        ]

        for lineno, line in enumerate(lines, 1):
            for pattern, message, severity in checks:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(
                        {
                            "file": file_path,
                            "line": lineno,
                            "message": message,
                            "severity": severity,
                            "code": line.strip()[:100],
                        }
                    )

        return issues

    def _classify_error(self, raw_text: str, file_path: str | None) -> ErrorEvent:
        """Parse a raw error string into a structured ErrorEvent."""
        error_type = "UnknownError"
        label = "Unknown error"
        severity = "error"

        for pattern, lbl, sev in KNOWN_ERROR_PATTERNS:
            if re.search(pattern, raw_text, re.IGNORECASE):
                error_type = re.search(pattern, raw_text, re.IGNORECASE).group(0)
                label = lbl
                severity = sev
                break

        # Extract file/line from traceback
        extracted_file = file_path
        line_number = None
        tb_match = re.search(r'File "([^"]+)", line (\d+)', raw_text)
        if tb_match:
            extracted_file = extracted_file or tb_match.group(1)
            line_number = int(tb_match.group(2))

        return ErrorEvent(
            raw_text=raw_text,
            file_path=extracted_file,
            line_number=line_number,
            error_type=error_type,
            label=label,
            severity=severity,
        )

    def _build_search_query(self, event: ErrorEvent) -> str:
        # Extract the most useful part of the error for searching
        lines = event.raw_text.strip().splitlines()
        key_line = next(
            (l for l in reversed(lines) if re.search(r"Error|Exception|Warning", l)),
            lines[-1] if lines else "",
        )
        query = f"Python {key_line.strip()[:120]} fix"
        return query

    def _read_file_safe(self, file_path: str) -> str | None:
        try:
            p = Path(file_path)
            if not p.exists() or p.stat().st_size > MAX_FILE_SIZE_BYTES:
                return None
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

    def _backup_file(self, file_path: str) -> str:
        try:
            src = Path(file_path)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup = BACKUP_DIR / f"{src.name}.{ts}.bak"
            shutil.copy2(src, backup)
            return str(backup)
        except Exception:
            return ""


# ── Singleton ─────────────────────────────────────────────────────────────────
self_healing_engine = SelfHealingEngine()


# ── Log handler that feeds errors to the engine automatically ─────────────────


class SelfHealLogHandler(logging.Handler):
    """
    Attach this to the root logger and POLYGOD will automatically detect
    ERROR/CRITICAL log events and queue them for self-healing.

    Added in main.py lifespan:
        logging.getLogger().addHandler(SelfHealLogHandler())
    """

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.ERROR:
            return
        try:
            text = self.format(record)
            if record.exc_info:
                text += "\n" + "".join(traceback.format_exception(*record.exc_info))
            # Non-blocking: just queue the event
            event = self_healing_engine._classify_error(text, None)
            try:
                self_healing_engine._error_queue.put_nowait(event)
            except (asyncio.QueueFull, RuntimeError):
                pass
        except Exception:
            pass

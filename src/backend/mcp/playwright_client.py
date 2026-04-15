"""
Playwright MCP Client — Connect to @playwright/mcp server over stdio.

This module provides Python bindings for browser automation via the Playwright
MCP server. It spawns the MCP server as a subprocess and communicates via stdio
using the MCP Python SDK.

Usage:
    from src.backend.mcp.playwright_client import playwright_client

    # Navigate to a URL
    await playwright_client.navigate("https://example.com")

    # Get accessibility snapshot
    snapshot = await playwright_client.snapshot()

    # Click an element
    await playwright_client.click("e5")

Configuration:
    Set PLAYWRIGHT_MCP_HEADLESS=true for headless mode
    Set PLAYWRIGHT_MCP_BROWSER=chromium|firefox|webkit
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


# ── Constants ───────────────────────────────────────────────────────────────────

DEFAULT_BROWSER = "chromium"
DEFAULT_TIMEOUT = 30


# ── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class BrowserSnapshot:
    """Accessibility snapshot of the current page."""

    url: str
    title: str
    tree: dict  # The accessibility tree
    raw: dict  # Full raw response


@dataclass
class NavigateResult:
    """Result from browser_navigate."""

    success: bool
    url: str
    title: str


# ── Playwright MCP Client ───────────────────────────────────────────────


class PlaywrightMCPClient:
    """
    Client for interacting with the Playwright MCP server.

    Manages the subprocess lifecycle and provides async methods for all
    Playwright MCP tools.
    """

    def __init__(
        self,
        headless: bool | None = None,
        browser: str = DEFAULT_BROWSER,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize the Playwright MCP client.

        Args:
            headless: Run browser in headless mode. Defaults to env var or False.
            browser: Browser to use (chromium, firefox, webkit).
            timeout: Default timeout for operations in seconds.
        """
        self._headless = headless
        self._browser = browser
        self._timeout = timeout
        self._session: ClientSession | None = None
        self._process_lock = asyncio.Lock()

    def _get_env(self) -> dict[str, str]:
        """Build environment for subprocess."""
        env = os.environ.copy()
        if self._headless is not None:
            env["PLAYWRIGHT_MCP_HEADLESS"] = str(self._headless).lower()
        if self._browser:
            env["PLAYWRIGHT_MCP_BROWSER"] = self._browser
        return env

    async def _ensure_session(self) -> ClientSession:
        """Ensure we have an active MCP session."""
        if self._session is not None:
            return self._session

        async with self._process_lock:
            if self._session is not None:
                return self._session

            # Determine headless from env if not set
            headless = self._headless
            if headless is None:
                headless = (
                    os.getenv("PLAYWRIGHT_MCP_HEADLESS", "false").lower() == "true"
                )

            server_params = StdioServerParameters(
                command="npx",
                args=["-y", "@playwright/mcp@latest"],
                env=self._get_env(),
            )

            logger.info(
                "Starting Playwright MCP server",
                browser=self._browser,
                headless=headless,
            )

            try:
                read, write = await stdio_client(server_params)
                self._session = ClientSession(read, write)
                await self._session.initialize()
                logger.info("Playwright MCP server connected")
            except Exception as exc:
                logger.error("Failed to connect to Playwright MCP server: %s", exc)
                raise

        return self._session

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Call a Playwright MCP tool.

        Args:
            tool_name: Name of the MCP tool (e.g., 'browser_navigate')
            arguments: Tool arguments as a dictionary
            timeout: Optional timeout override in seconds

        Returns:
            Tool result as a dictionary
        """
        session = await self._ensure_session()

        try:
            result = await session.call_tool(
                tool_name,
                arguments,
                timeout=timeout or self._timeout,
            )

            # Parse the result - MCP returns content blocks
            if hasattr(result, "content") and result.content:
                # Extract text from content blocks
                texts = []
                for block in result.content:
                    if hasattr(block, "text"):
                        texts.append(block.text)
                    elif isinstance(block, dict):
                        texts.append(json.dumps(block))

                if texts:
                    # Try to parse as JSON, fallback to raw text
                    try:
                        return json.loads(texts[0])
                    except json.JSONDecodeError:
                        return {"raw": texts[0]}

            return {"status": "ok"}

        except Exception as exc:
            logger.error("Playwright MCP tool call failed: %s", exc)
            return {"error": str(exc)}

    # ── Public API: Core Tools ─────────────────────────────────────────────

    async def navigate(
        self,
        url: str,
        timeout: int | None = None,
    ) -> NavigateResult:
        """
        Navigate to a URL.

        Args:
            url: The URL to navigate to
            timeout: Optional timeout override

        Returns:
            NavigateResult with success status and page info
        """
        result = await self._call_tool(
            "browser_navigate",
            {"url": url},
            timeout=timeout,
        )

        return NavigateResult(
            success=result.get("success", True),
            url=result.get("url", url),
            title=result.get("title", ""),
        )

    async def snapshot(
        self,
        timeout: int | None = None,
    ) -> BrowserSnapshot:
        """
        Get accessibility snapshot of current page.

        Args:
            timeout: Optional timeout override

        Returns:
            BrowserSnapshot with page data and accessibility tree
        """
        result = await self._call_tool(
            "browser_snapshot",
            {},
            timeout=timeout,
        )

        return BrowserSnapshot(
            url=result.get("url", ""),
            title=result.get("title", ""),
            tree=result.get("tree", {}),
            raw=result,
        )

    async def click(
        self,
        element_ref: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Click an element by its accessibility reference.

        Args:
            element_ref: The element reference (e.g., 'e5')
            timeout: Optional timeout override

        Returns:
            Result dictionary
        """
        return await self._call_tool(
            "browser_click",
            {"ref": element_ref},
            timeout=timeout,
        )

    async def hover(
        self,
        element_ref: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Hover over an element by its accessibility reference.

        Args:
            element_ref: The element reference
            timeout: Optional timeout override

        Returns:
            Result dictionary
        """
        return await self._call_tool(
            "browser_hover",
            {"ref": element_ref},
            timeout=timeout,
        )

    async def type(
        self,
        element_ref: str,
        text: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Type text into an input element.

        Args:
            element_ref: The element reference
            text: Text to type
            timeout: Optional timeout override

        Returns:
            Result dictionary
        """
        return await self._call_tool(
            "browser_type",
            {"ref": element_ref, "text": text},
            timeout=timeout,
        )

    async def press(
        self,
        element_ref: str,
        key: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Press a key on an element.

        Args:
            element_ref: The element reference
            key: Key to press (e.g., 'Enter', 'Tab')
            timeout: Optional timeout override

        Returns:
            Result dictionary
        """
        return await self._call_tool(
            "browser_press",
            {"ref": element_ref, "key": key},
            timeout=timeout,
        )

    async def select_option(
        self,
        element_ref: str,
        value: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Select an option from a dropdown.

        Args:
            element_ref: The select element reference
            value: Value to select
            timeout: Optional timeout override

        Returns:
            Result dictionary
        """
        return await self._call_tool(
            "browser_select_option",
            {"ref": element_ref, "value": value},
            timeout=timeout,
        )

    async def check(
        self,
        element_ref: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Check a checkbox or radio button.

        Args:
            element_ref: The element reference
            timeout: Optional timeout override

        Returns:
            Result dictionary
        """
        return await self._call_tool(
            "browser_check",
            {"ref": element_ref},
            timeout=timeout,
        )

    async def uncheck(
        self,
        element_ref: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Uncheck a checkbox.

        Args:
            element_ref: The element reference
            timeout: Optional timeout override

        Returns:
            Result dictionary
        """
        return await self._call_tool(
            "browser_uncheck",
            {"ref": element_ref},
            timeout=timeout,
        )

    # ── Public API: Navigation Tools ──────────────────────────────────────

    async def go_back(self, timeout: int | None = None) -> dict[str, Any]:
        """Navigate back in history."""
        return await self._call_tool("browser_navigate_back", {}, timeout=timeout)

    async def go_forward(self, timeout: int | None = None) -> dict[str, Any]:
        """Navigate forward in history."""
        return await self._call_tool("browser_navigate_forward", {}, timeout=timeout)

    async def reload(self, timeout: int | None = None) -> dict[str, Any]:
        """Reload the current page."""
        return await self._call_tool("browser_reload", {}, timeout=timeout)

    # ── Public API: Screenshot ─────────────────────────────────────────────

    async def screenshot(
        self,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Take a screenshot of the current page.

        Returns base64-encoded image data.
        """
        return await self._call_tool("browser_screenshot", {}, timeout=timeout)

    # ── Public API: Console Logs ──────────────────────────────────────────

    async def get_console_logs(
        self,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Get console logs from the page."""
        return await self._call_tool("browser_console_logs", {}, timeout=timeout)

    # ── Public API: Storage ───────────────────────────────────────────────

    async def get_local_storage(
        self,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Get local storage data."""
        return await self._call_tool("browser_get_local_storage", {}, timeout=timeout)

    async def set_local_storage(
        self,
        key: str,
        value: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Set a local storage value."""
        return await self._call_tool(
            "browser_set_local_storage",
            {"key": key, "value": value},
            timeout=timeout,
        )

    async def clear_local_storage(
        self,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Clear local storage."""
        return await self._call_tool("browser_clear_local_storage", {}, timeout=timeout)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the MCP session and cleanup."""
        if self._session is not None:
            try:
                await self._session.close()
            except Exception as exc:
                logger.debug("Error closing MCP session: %s", exc)
            self._session = None
            logger.info("Playwright MCP server disconnected")


# ── Singleton ─────────────────────────────────────────────────────────────

_playwright_client: PlaywrightMCPClient | None = None


def get_playwright_client(
    headless: bool | None = None,
    browser: str = DEFAULT_BROWSER,
    timeout: int = DEFAULT_TIMEOUT,
) -> PlaywrightMCPClient:
    """
    Get or create the singleton Playwright MCP client.

    Args:
        headless: Run browser in headless mode
        browser: Browser to use
        timeout: Default timeout

    Returns:
        PlaywrightMCPClient instance
    """
    global _playwright_client
    if _playwright_client is None:
        _playwright_client = PlaywrightMCPClient(
            headless=headless,
            browser=browser,
            timeout=timeout,
        )
    return _playwright_client


# Convenience singleton for import
playwright_client = get_playwright_client()

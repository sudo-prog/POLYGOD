"""
MCP (Model Context Protocol) integrations for POLYGOD.

Currently provides:
- Playwright MCP client for browser automation
"""

from src.backend.mcp.playwright_client import (
    PlaywrightMCPClient,
    get_playwright_client,
    playwright_client,
)

__all__ = [
    "PlaywrightMCPClient",
    "get_playwright_client",
    "playwright_client",
]

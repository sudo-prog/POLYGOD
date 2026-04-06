"""
Security Headers Middleware - Custom implementation for Starlette.

Provides security headers like X-Content-Type-Options, X-Frame-Options, etc.
"""

from starlette.middleware import Middleware as StarletteMiddleware
from starlette.types import ASGIApp, Receive, Send


class SecurityHeadersMiddleware(StarletteMiddleware):
    """Middleware to add security headers to responses."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.app = app

    async def __call__(self, scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Headers to add
        headers = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"SAMEORIGIN"),
            (b"x-xss-protection", b"1; mode=block"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
        ]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Add headers to the response
                headers_list = list(message.get("headers", []))
                headers_list.extend(headers)
                message["headers"] = headers_list
            await send(message)

        await self.app(scope, receive, send_wrapper)

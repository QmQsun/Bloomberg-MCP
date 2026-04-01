#!/usr/bin/env python3
"""
Bloomberg MCP Server - FastMCP wrapper for Bloomberg data access.

This server exposes Bloomberg data tools via MCP protocol, enabling
LLMs to fetch market data, reference data, and historical data.

Architecture:
    server.py       - FastMCP init, handler registration, entry point (this file)
    models/         - Pydantic input models and enums
    handlers/       - @mcp.tool handler functions (one file per domain)
    formatters.py   - Response formatting helpers
    utils.py        - Shared utilities (_expand_fields, _truncate_response, etc.)
    core/           - Bloomberg session, request builders, response parsers,
                      circuit breaker, throttle, validators, structured logging
    tools/          - Lower-level tool implementations
"""

import logging
import os

# Initialize structured logging before anything else
from bloomberg_mcp.core.logging import setup_logging

_log_level = os.environ.get("BLOOMBERG_MCP_LOG_LEVEL", "INFO").upper()
_structured = os.environ.get("BLOOMBERG_MCP_LOG_FORMAT", "structured") == "structured"
setup_logging(level=getattr(logging, _log_level, logging.INFO), structured=_structured)

logger = logging.getLogger(__name__)

# Import the singleton mcp instance (see _mcp_instance.py for why)
from bloomberg_mcp._mcp_instance import mcp  # noqa: F401, E402

# Register all tool handlers (each module decorates functions with @mcp.tool)
import bloomberg_mcp.handlers  # noqa: E402, F401


# ============================================================================
# Server Entry Point
# ============================================================================

def main():
    """Main entry point for the Bloomberg MCP server."""
    import sys

    # Check for transport argument
    transport = "stdio"
    # Default to localhost for security — 0.0.0.0 exposes to entire network
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8080"))

    for arg in sys.argv[1:]:
        if arg == "--http":
            transport = "streamable-http"
        elif arg == "--sse":
            transport = "sse"
        elif arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg.startswith("--host="):
            host = arg.split("=")[1]

    logger.info(
        "Bloomberg MCP server starting",
        extra={"tool": "server", "securities": None, "duration_ms": 0,
               "cache_hit": False},
    )

    if transport == "stdio":
        mcp.run()
    else:
        # For HTTP/SSE transport, use uvicorn directly
        import uvicorn

        if transport == "sse":
            base_app = mcp.sse_app()
        else:
            # streamable_http_app() requires mcp >= 1.18; fall back to sse_app()
            try:
                base_app = mcp.streamable_http_app()
            except AttributeError:
                logger.warning(
                    "streamable_http_app() not available (mcp < 1.18), "
                    "falling back to sse_app()"
                )
                base_app = mcp.sse_app()

        # Optional API key authentication for HTTP/SSE transport
        api_key = os.environ.get("MCP_API_KEY")
        if api_key:
            base_app = _ApiKeyMiddleware(base_app, api_key)
            logger.info("API key authentication enabled for HTTP transport")

        # Host header rewrite for Tailscale/remote access
        # Only needed when explicitly binding to 0.0.0.0
        if host == "0.0.0.0":
            base_app = _AllowAllHostsMiddleware(base_app)
            logger.warning(
                "Server binding to 0.0.0.0 — accessible from network. "
                "Set MCP_API_KEY for authentication."
            )

        uvicorn.run(
            base_app,
            host=host,
            port=port,
            log_level="info"
        )


class _AllowAllHostsMiddleware:
    """Rewrite Host header to localhost for Tailscale/reverse proxy compat."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = [(k, v) for k, v in scope["headers"] if k != b"host"]
            headers.append((b"host", b"localhost:8080"))
            scope = dict(scope, headers=headers)
        await self.app(scope, receive, send)


class _ApiKeyMiddleware:
    """Simple Bearer token authentication for HTTP/SSE transport."""

    def __init__(self, app, api_key: str):
        self.app = app
        self._api_key = api_key

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode()
            if not auth.startswith("Bearer ") or auth[7:] != self._api_key:
                # Return 401
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "Unauthorized. Set Authorization: Bearer <MCP_API_KEY>"}',
                })
                return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    main()

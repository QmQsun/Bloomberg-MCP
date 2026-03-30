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
    core/           - Bloomberg session, request builders, response parsers
    tools/          - Lower-level tool implementations
"""

import logging
import os

logger = logging.getLogger(__name__)

# Import the singleton mcp instance (see _mcp_instance.py for why)
from bloomberg_mcp._mcp_instance import mcp  # noqa: F401

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
    host = os.environ.get("MCP_HOST", "0.0.0.0")
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

        # Wrap app to allow all hosts (needed for Tailscale/remote access)
        class AllowAllHostsMiddleware:
            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    headers = [(k, v) for k, v in scope["headers"] if k != b"host"]
                    headers.append((b"host", b"localhost:8080"))
                    scope = dict(scope, headers=headers)
                await self.app(scope, receive, send)

        app = AllowAllHostsMiddleware(base_app)

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )


if __name__ == "__main__":
    main()

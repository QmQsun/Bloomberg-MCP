"""
Singleton FastMCP instance.

This module exists to avoid the classic Python __main__ double-import problem.
When server.py is run via `python -m bloomberg_mcp.server`, Python loads it
under the key "__main__", NOT "bloomberg_mcp.server". Handlers that do
`from bloomberg_mcp.server import mcp` trigger a SECOND load of server.py
under key "bloomberg_mcp.server", creating a separate mcp object. Tools
register on the second instance, but main() runs the first — 0 tools.

By placing `mcp` in its own module, both server.py and all handlers import
from the same sys.modules key ("bloomberg_mcp._mcp_instance"), guaranteeing
a single mcp instance.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bloomberg_mcp")

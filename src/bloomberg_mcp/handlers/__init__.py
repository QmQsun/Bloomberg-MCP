"""MCP tool handlers for Bloomberg data access.

Each module registers its tools with the shared `mcp` server instance.
Import all handler modules to trigger tool registration.
"""

from . import reference
from . import historical
from . import intraday
from . import search
from . import screening
from . import bulk
from . import estimates
from . import technical
from . import ownership
from . import supply_chain
from . import bql
from . import calendars

# Bloomberg MCP

Data access layer for Bloomberg Terminal via the Bloomberg API (blpapi).

## Installation

```bash
# 1. Install Bloomberg C++ SDK and set BLPAPI_ROOT
export BLPAPI_ROOT=/path/to/blpapi_cpp_3.x.x.x

# 2. Install blpapi Python SDK
pip install -e ../blpapi-3.25.7.1

# 3. Install this package
pip install -e .
```

## Quick Start

```python
from bloomberg_mcp.tools import get_reference_data, get_historical_data

# Get current prices
data = get_reference_data(
    securities=["AAPL US Equity", "MSFT US Equity"],
    fields=["PX_LAST", "PE_RATIO", "DIVIDEND_YIELD"]
)
for sec in data:
    print(f"{sec.security}: ${sec.fields.get('PX_LAST')}")

# Get historical data
hist = get_historical_data(
    securities=["SPY US Equity"],
    fields=["PX_LAST", "VOLUME"],
    start_date="20240101",
    end_date="20241231",
    periodicity="DAILY"
)
```

## Available Tools

| Function | Description |
|----------|-------------|
| `get_reference_data()` | Current field values for securities |
| `get_historical_data()` | Time series data |
| `get_intraday_bars()` | OHLCV bar data |
| `get_intraday_ticks()` | Raw tick data |
| `search_securities()` | Find securities by name |
| `search_fields()` | Discover Bloomberg fields |
| `get_field_info()` | Field metadata |

## MCP Server (Claude Code Integration)

This package includes an MCP server that exposes Bloomberg tools to Claude Code CLI.

### Setup for Claude Code

1. **Install dependencies:**
   ```bash
   pip install -e .
   ```

2. **Configure Claude Code** (already done if using this repo):

   The `.claude.json` in the parent directory configures the MCP server:
   ```json
   {
     "mcpServers": {
       "bloomberg-mcp": {
         "command": "python",
         "args": ["-m", "bloomberg_mcp.server"],
         "cwd": "path/to/bloomberg-mcp",
         "env": {
           "BLOOMBERG_HOST": "localhost",
           "BLOOMBERG_PORT": "8194"
         }
       }
     }
   }
   ```

3. **Verify Bloomberg Terminal is running** with API enabled.

4. **Restart Claude Code** to load the MCP server.

### Running the Server Manually

```bash
# Stdio transport (default, for Claude Code)
python -m bloomberg_mcp.server

# HTTP transport (for web clients)
python -m bloomberg_mcp.server --http --port=8080

# SSE transport (for streaming)
python -m bloomberg_mcp.server --sse --port=8080
```

### MCP Tools Available

| Tool | Description |
|------|-------------|
| `bloomberg_get_reference_data` | Get current field values |
| `bloomberg_get_historical_data` | Get historical time series |
| `bloomberg_get_intraday_bars` | Get intraday OHLCV bars |
| `bloomberg_get_intraday_ticks` | Get raw tick data |
| `bloomberg_search_securities` | Search for securities |
| `bloomberg_search_fields` | Discover Bloomberg fields |
| `bloomberg_get_field_info` | Get field metadata |

### Docker Setup (Optional)

For running the MCP server in Docker:

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f bloomberg-mcp
```

Note: Docker requires blpapi to be properly installed in the container and
network access to Bloomberg Terminal on the host.

## Documentation

See [CLAUDE.md](CLAUDE.md) for:
- Full API reference
- Usage patterns and examples
- Common Bloomberg fields
- Architecture overview

## Requirements

- Python 3.10+
- Bloomberg Terminal or B-PIPE connection
- Bloomberg C++ SDK
- blpapi Python SDK

## License

MIT

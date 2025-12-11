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

"""Historical data (BDH) tool handler."""

import logging

from bloomberg_mcp.server import mcp

logger = logging.getLogger(__name__)
from bloomberg_mcp.models import HistoricalDataInput
from bloomberg_mcp.utils import _expand_fields
from bloomberg_mcp.formatters import _format_historical_data, _smart_truncate_historical_data


@mcp.tool(
    name="bloomberg_get_historical_data",
    annotations={
        "title": "Get Historical Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_historical_data(params: HistoricalDataInput) -> str:
    """
    Get historical time series data for securities from Bloomberg.

    Fetches historical price and fundamental data over a date range.
    Supports daily, weekly, monthly, quarterly, and yearly periodicity.

    Args:
        params: HistoricalDataInput containing securities, fields, date range, and periodicity

    Returns:
        JSON or Markdown formatted time series data

    Example:
        securities=["SPY US Equity"], fields=["PX_LAST"],
        start_date="20240101", end_date="20241231", periodicity="DAILY"
        start_date="2024-01-01", end_date="2024-12-31"  # ISO format also works
    """
    try:
        from bloomberg_mcp.tools import get_historical_data

        expanded_fields = _expand_fields(params.fields)

        data = get_historical_data(
            securities=params.securities,
            fields=expanded_fields,
            start_date=params.start_date,
            end_date=params.end_date,
            periodicity=params.periodicity
        )

        result = _format_historical_data(data, params.response_format)
        return _smart_truncate_historical_data(data, result)

    except Exception as e:
        return f"Error fetching historical data: {str(e)}"

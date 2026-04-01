"""Historical data (BDH) tool handler."""

import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import HistoricalDataInput
from bloomberg_mcp.utils import _expand_fields
from bloomberg_mcp.formatters import _format_historical_data, _smart_truncate_historical_data
from bloomberg_mcp.core.logging import log_tool_call
from bloomberg_mcp.core.validators import validate_field_count, validate_historical_response
from bloomberg_mcp.handlers._common import pre_request, fallback_or_error

logger = logging.getLogger(__name__)


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
    cache_key = {
        "request_type": "historical",
        "securities": params.securities,
        "fields": params.fields,
        "extra": f"{params.start_date}_{params.end_date}_{params.periodicity}",
    }

    with log_tool_call("bloomberg_get_historical_data",
                       securities=params.securities,
                       fields=params.fields) as ctx:
        try:
            pre_request()

            from bloomberg_mcp.tools import get_historical_data

            expanded_fields = _expand_fields(params.fields)
            validate_field_count(expanded_fields, "historical")

            data = get_historical_data(
                securities=params.securities,
                fields=expanded_fields,
                start_date=params.start_date,
                end_date=params.end_date,
                periodicity=params.periodicity
            )

            # Post-response quality gate
            warnings = validate_historical_response(
                data, params.start_date, params.end_date
            )
            if warnings:
                ctx["error_count"] = len(warnings)

            result = _format_historical_data(data, params.response_format)
            result = _smart_truncate_historical_data(data, result)
            ctx["result_size"] = len(result)
            return result

        except Exception as e:
            ctx["error"] = True
            return fallback_or_error(e, "bloomberg_get_historical_data", cache_key)

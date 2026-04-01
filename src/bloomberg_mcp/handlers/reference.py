"""Reference data (BDP) tool handler."""

import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import ReferenceDataInput
from bloomberg_mcp.utils import _expand_fields
from bloomberg_mcp.formatters import _format_security_data, _smart_truncate_security_data
from bloomberg_mcp.core.logging import log_tool_call
from bloomberg_mcp.core.validators import validate_field_count, validate_reference_response
from bloomberg_mcp.handlers._common import pre_request, fallback_or_error

logger = logging.getLogger(__name__)


@mcp.tool(
    name="bloomberg_get_reference_data",
    annotations={
        "title": "Get Reference Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_reference_data(params: ReferenceDataInput) -> str:
    """
    Get current field values for one or more securities from Bloomberg.

    This tool fetches real-time or static reference data for securities.
    Use it to get current prices, valuations, fundamentals, and other metrics.

    Common fields:
    - Price: PX_LAST, PX_BID, PX_ASK, PX_OPEN, PX_HIGH, PX_LOW, VOLUME
    - Valuation: PE_RATIO, PX_TO_BOOK_RATIO, EV_TO_EBITDA, DIVIDEND_YIELD
    - Fundamentals: RETURN_ON_EQUITY, GROSS_MARGIN, MARKET_CAP

    Args:
        params: ReferenceDataInput containing securities, fields, and options

    Returns:
        JSON or Markdown formatted data with field values for each security

    Example:
        securities=["AAPL US Equity"], fields=["PX_LAST", "PE_RATIO"]
        securities=["AAPL US Equity"], fields=["VALUATION", "MOMENTUM"]  # FieldSet shortcuts
    """
    cache_key = {
        "request_type": "reference",
        "securities": params.securities,
        "fields": params.fields,
        "overrides": params.overrides,
    }

    with log_tool_call("bloomberg_get_reference_data",
                       securities=params.securities,
                       fields=params.fields) as ctx:
        try:
            pre_request()

            from bloomberg_mcp.tools import get_reference_data

            expanded_fields = _expand_fields(params.fields)
            validate_field_count(expanded_fields, "reference")

            data = get_reference_data(
                securities=params.securities,
                fields=expanded_fields,
                overrides=params.overrides
            )

            # Post-response quality gate
            warnings = validate_reference_response(data, expanded_fields)
            if warnings:
                ctx["error_count"] = len(warnings)

            result = _format_security_data(data, params.response_format)
            result = _smart_truncate_security_data(data, result)
            ctx["result_size"] = len(result)
            return result

        except Exception as e:
            ctx["error"] = True
            return fallback_or_error(e, "bloomberg_get_reference_data", cache_key)

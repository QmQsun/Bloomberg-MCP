"""Bulk data (BDS) tool handler."""

import json
import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import BulkDataInput, ResponseFormat
from bloomberg_mcp.utils import _truncate_response
from bloomberg_mcp.core.logging import log_tool_call
from bloomberg_mcp.core.validators import validate_bulk_response
from bloomberg_mcp.handlers._common import pre_request, fallback_or_error

logger = logging.getLogger(__name__)


@mcp.tool(
    name="bloomberg_get_bulk_data",
    annotations={
        "title": "Get Bulk Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_bulk_data(params: BulkDataInput) -> str:
    """
    Get Bloomberg bulk data (BDS) — returns tabular/array data.

    Unlike reference data (BDP) which returns single values,
    bulk data returns lists/tables of related information.

    Common BDS fields:
    - TOP_20_HOLDERS_PUBLIC_FILINGS — Top 20 shareholders
    - DVD_HIST_ALL — Complete dividend history
    - SUPPLY_CHAIN_SUPPLIERS — Supplier list with revenue exposure
    - SUPPLY_CHAIN_CUSTOMERS — Customer list with revenue exposure
    - SUPPLY_CHAIN_COMPETITORS — Competitor list
    - INDX_MEMBERS — Index constituents
    - ANALYST_RECOMMENDATIONS — Analyst ratings detail
    - ERN_ANN_DT_AND_PER — Earnings announcement dates
    - BOARD_OF_DIRECTORS — Board members
    - EARN_ANN_DT_TIME_HIST_WITH_EPS — Historical earnings with actual EPS

    Args:
        params: BulkDataInput containing security, BDS field, and options

    Returns:
        JSON or Markdown formatted tabular data

    Example:
        security="AAPL US Equity", field="TOP_20_HOLDERS_PUBLIC_FILINGS"
        security="MSFT US Equity", field="DVD_HIST_ALL"
    """
    cache_key = {
        "request_type": "bulk",
        "securities": [params.security],
        "fields": [params.field],
        "overrides": params.overrides,
    }

    with log_tool_call("bloomberg_get_bulk_data",
                       securities=[params.security],
                       fields=[params.field]) as ctx:
        try:
            pre_request()

            from bloomberg_mcp.tools import get_reference_data

            data = get_reference_data(
                securities=[params.security],
                fields=[params.field],
                overrides=params.overrides
            )

            if not data:
                return f"No data returned for {params.security} / {params.field}"

            sec_data = data[0]

            if sec_data.errors:
                return f"Error for {params.security}: {', '.join(sec_data.errors)}"

            field_value = sec_data.fields.get(params.field)

            # Quality gate: validate bulk response
            warnings = validate_bulk_response(field_value, params.field, params.security)
            if warnings:
                ctx["error_count"] = len(warnings)
                # If it's a scalar, return guidance
                for w in warnings:
                    if w.code == "SCALAR_BULK_FIELD":
                        return json.dumps({
                            "security": params.security,
                            "field": params.field,
                            "value": field_value,
                            "note": str(w),
                        }, indent=2, default=str)

            if field_value is None:
                return f"Field '{params.field}' returned no data for {params.security}"

            # BDS fields return lists of dicts via toPy()
            if isinstance(field_value, list):
                rows = field_value
            elif isinstance(field_value, dict):
                rows = [field_value]
            else:
                return json.dumps({
                    "security": params.security,
                    "field": params.field,
                    "value": field_value,
                    "note": "This field returns a scalar value. Use bloomberg_get_reference_data instead for better results."
                }, indent=2, default=str)

            total_rows = len(rows)
            truncated = total_rows > params.max_rows
            rows = rows[:params.max_rows]

            columns = list(rows[0].keys()) if rows else []

            if params.response_format == ResponseFormat.MARKDOWN:
                lines = [
                    f"## Bulk Data: {params.security}",
                    f"**Field**: {params.field}",
                    f"**Total rows**: {total_rows}" + (f" (showing {params.max_rows})" if truncated else ""),
                    ""
                ]

                if rows:
                    lines.append("| " + " | ".join(columns) + " |")
                    lines.append("|" + "---|" * len(columns))

                    for row in rows:
                        values = []
                        for col in columns:
                            val = row.get(col, "")
                            if isinstance(val, float):
                                val = f"{val:.4f}"
                            val_str = str(val)
                            if len(val_str) > 30:
                                val_str = val_str[:27] + "..."
                            values.append(val_str)
                        lines.append("| " + " | ".join(values) + " |")

                result = "\n".join(lines)
            else:
                result = json.dumps({
                    "security": params.security,
                    "field": params.field,
                    "total_rows": total_rows,
                    "truncated": truncated,
                    "columns": columns,
                    "data": rows,
                }, indent=2, default=str)

            ctx["result_size"] = len(result)
            return _truncate_response(result)

        except Exception as e:
            ctx["error"] = True
            return fallback_or_error(e, "bloomberg_get_bulk_data", cache_key)

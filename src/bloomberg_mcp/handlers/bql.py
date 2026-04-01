"""Bloomberg Query Language (BQL) tool handler."""

import json
import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import BQLInput, ResponseFormat
from bloomberg_mcp.utils import _truncate_response, BLOOMBERG_HOST, BLOOMBERG_PORT
from bloomberg_mcp.core.logging import log_tool_call
from bloomberg_mcp.handlers._common import pre_request, fallback_or_error

logger = logging.getLogger(__name__)


@mcp.tool(
    name="bloomberg_run_bql",
    annotations={
        "title": "Run BQL Query",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_run_bql(params: BQLInput) -> str:
    """
    Run a Bloomberg Query Language (BQL) expression.

    BQL is Bloomberg's analytical query language that enables complex
    data retrieval, screening, and computation in a single expression.

    SERVICE: //blp/bqlsvc (available on Desktop API with Professional license)

    SYNTAX EXAMPLES:
    - get(px_last()) for(['AAPL US Equity'])
    - get(px_last(), pe_ratio()) for(['AAPL US Equity', 'MSFT US Equity'])
    - get(avg(px_last(dates=range(-30d,0d)))) for(['SPY US Equity'])
    - get(px_last()) for(members('SPX Index')) with(limit=10)
    - get(group(px_last(), GICS_SECTOR_NAME)) for(members('SPX Index'))

    NOTE: //blp/bqlsvc requires Bloomberg Professional license.
    If the service is unavailable, a graceful error is returned.

    Args:
        params: BQLInput with BQL expression

    Returns:
        JSON or Markdown formatted query results

    Example:
        expression="get(px_last(), pe_ratio()) for(['AAPL US Equity'])"
    """
    with log_tool_call("bloomberg_run_bql") as ctx:
        try:
            pre_request()

            from bloomberg_mcp.core.session import BloombergSession

            session = BloombergSession.get_instance(host=BLOOMBERG_HOST, port=BLOOMBERG_PORT)
            if not session.is_connected():
                if not session.connect():
                    return "Error: Failed to connect to Bloomberg Terminal."

            service = session.get_service("//blp/bqlsvc")
            if service is None:
                return (
                    "Error: //blp/bqlsvc service is not available. "
                    "BQL requires Bloomberg Professional license and Desktop API. "
                    "The service may not be enabled on this terminal. "
                    "Try using bloomberg_get_reference_data or bloomberg_dynamic_screen as alternatives."
                )

            request = service.createRequest("sendQuery")
            request.set("expression", params.expression)

            raw_results = session.send_request(
                request,
                service_name="//blp/bqlsvc",
            )

            if not raw_results:
                return f"No results returned for BQL expression: {params.expression}"

            parsed = _parse_bql_results(raw_results)

            if params.response_format == ResponseFormat.MARKDOWN:
                lines = [
                    "## BQL Query Results",
                    f"**Expression**: `{params.expression}`",
                    ""
                ]

                if parsed.get("errors"):
                    lines.append(f"**Errors**: {', '.join(parsed['errors'])}")
                    lines.append("")

                records = parsed.get("records", [])
                if records:
                    columns = list(records[0].keys())
                    lines.append("| " + " | ".join(columns) + " |")
                    lines.append("|" + "---|" * len(columns))
                    for row in records[:100]:
                        vals = []
                        for col in columns:
                            v = row.get(col, "")
                            if isinstance(v, float):
                                v = f"{v:.4f}"
                            val_str = str(v)
                            if len(val_str) > 30:
                                val_str = val_str[:27] + "..."
                            vals.append(val_str)
                        lines.append("| " + " | ".join(vals) + " |")
                    if len(records) > 100:
                        lines.append(f"\n*... and {len(records) - 100} more rows*")
                else:
                    lines.append("*No records returned*")

                result = "\n".join(lines)
            else:
                result = json.dumps({
                    "expression": params.expression,
                    **parsed,
                }, indent=2, default=str)

            ctx["result_size"] = len(result)
            return _truncate_response(result)

        except Exception as e:
            ctx["error"] = True
            return fallback_or_error(e, "bloomberg_run_bql")


def _parse_bql_results(raw_results: list) -> dict:
    """Parse raw BQL toPy() results into a structured format."""
    records = []
    errors = []
    columns = set()

    for msg_data in raw_results:
        if not isinstance(msg_data, dict):
            continue

        if "responseError" in msg_data:
            errors.append(str(msg_data["responseError"]))
            continue

        results = msg_data.get("results", msg_data)

        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    records.append(item)
                    columns.update(item.keys())
        elif isinstance(results, dict):
            for key, val in results.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            records.append(item)
                            columns.update(item.keys())
                elif isinstance(val, dict):
                    records.append({key: val})
                    columns.add(key)

    return {
        "records": records,
        "columns": sorted(columns) if columns else [],
        "total_records": len(records),
        "errors": errors,
    }

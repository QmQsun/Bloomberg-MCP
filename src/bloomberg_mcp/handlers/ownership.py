"""Ownership analysis tool handler — combines BDP summary + BDS holder list."""

import json
import logging

from bloomberg_mcp.server import mcp
from bloomberg_mcp.models import OwnershipInput, ResponseFormat
from bloomberg_mcp.utils import _truncate_response

logger = logging.getLogger(__name__)

# BDP fields for ownership summary
OWNERSHIP_SUMMARY_FIELDS = [
    "PCT_HELD_BY_INSIDERS",
    "PCT_HELD_BY_INSTITUTIONS",
    "NUM_OF_INSTITUTIONAL_HOLDERS",
    "SHORT_INT_RATIO",
    "SHORT_INT",
    "PUT_CALL_OPEN_INTEREST_RATIO",
    "EQY_SH_OUT",
]


@mcp.tool(
    name="bloomberg_get_ownership",
    annotations={
        "title": "Get Ownership",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_ownership(params: OwnershipInput) -> str:
    """
    Get ownership analysis: summary metrics + top holder list.

    Combines two data sources:
    1. BDP (summary): insider/institutional ownership %, short interest, put/call ratio
    2. BDS (holders): top N holders with position size and % outstanding

    Args:
        params: OwnershipInput with security and max_holders

    Returns:
        JSON or Markdown with ownership summary and holder table

    Example:
        security="AAPL US Equity", max_holders=20
    """
    try:
        from bloomberg_mcp.tools import get_reference_data

        # 1. Fetch BDP summary metrics
        summary_data = get_reference_data(
            securities=[params.security],
            fields=OWNERSHIP_SUMMARY_FIELDS
        )

        summary = {}
        summary_errors = []
        if summary_data:
            summary = summary_data[0].fields
            summary_errors = summary_data[0].errors

        # 2. Fetch BDS top holders list
        holder_data = get_reference_data(
            securities=[params.security],
            fields=["TOP_20_HOLDERS_PUBLIC_FILINGS"]
        )

        holders = []
        holder_errors = []
        if holder_data:
            raw = holder_data[0].fields.get("TOP_20_HOLDERS_PUBLIC_FILINGS", [])
            holder_errors = holder_data[0].errors
            if isinstance(raw, list):
                holders = raw[:params.max_holders]

        all_errors = summary_errors + holder_errors

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [
                f"## Ownership: {params.security}",
                ""
            ]

            if all_errors:
                lines.append(f"**Errors**: {', '.join(all_errors)}")
                lines.append("")

            # Summary section
            lines.append("### Summary")
            for field_name, value in summary.items():
                label = field_name.replace("_", " ").title()
                if isinstance(value, float):
                    lines.append(f"- **{label}**: {value:.2f}")
                else:
                    lines.append(f"- **{label}**: {value}")
            lines.append("")

            # Holders table
            if holders:
                lines.append(f"### Top {len(holders)} Holders")
                columns = list(holders[0].keys()) if holders else []
                if columns:
                    lines.append("| " + " | ".join(columns) + " |")
                    lines.append("|" + "---|" * len(columns))
                    for row in holders:
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

            result = "\n".join(lines)
        else:
            result = json.dumps({
                "security": params.security,
                "summary": summary,
                "holders": {
                    "total_returned": len(holders),
                    "data": holders,
                },
                "errors": all_errors,
            }, indent=2, default=str)

        return _truncate_response(result)

    except Exception as e:
        logger.exception("Error fetching ownership data")
        return f"Error fetching ownership data: {str(e)}"

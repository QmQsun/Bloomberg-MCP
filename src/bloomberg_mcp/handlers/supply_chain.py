"""Supply chain analysis tool handler."""

import json
import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import SupplyChainInput, ResponseFormat
from bloomberg_mcp.utils import _truncate_response

logger = logging.getLogger(__name__)

# BDS field mapping for each relationship type
SUPPLY_CHAIN_FIELDS = {
    "suppliers": "SUPPLY_CHAIN_SUPPLIERS",
    "customers": "SUPPLY_CHAIN_CUSTOMERS",
    "competitors": "SUPPLY_CHAIN_COMPETITORS",
}


@mcp.tool(
    name="bloomberg_get_supply_chain",
    annotations={
        "title": "Get Supply Chain",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_supply_chain(params: SupplyChainInput) -> str:
    """
    Get supply chain relationships: suppliers, customers, and competitors.

    Uses Bloomberg BDS fields to retrieve supply chain data with
    revenue exposure percentages where available.

    RELATIONSHIP TYPES:
    - suppliers: Companies that supply to the target
    - customers: Companies that are customers of the target
    - competitors: Companies that compete with the target
    - all: Fetch all three (default)

    Args:
        params: SupplyChainInput with security, relationship type, max_rows

    Returns:
        JSON or Markdown with supply chain data by relationship type

    Example:
        security="AAPL US Equity", relationship="all"
        security="TSLA US Equity", relationship="suppliers"
    """
    try:
        from bloomberg_mcp.tools import get_reference_data

        # Determine which relationships to fetch
        if params.relationship == "all":
            rel_types = list(SUPPLY_CHAIN_FIELDS.keys())
        else:
            rel_types = [params.relationship]

        results = {}
        all_errors = []

        for rel_type in rel_types:
            bds_field = SUPPLY_CHAIN_FIELDS[rel_type]

            data = get_reference_data(
                securities=[params.security],
                fields=[bds_field]
            )

            rows = []
            if data:
                raw = data[0].fields.get(bds_field, [])
                if data[0].errors:
                    all_errors.extend(data[0].errors)
                if isinstance(raw, list):
                    rows = raw[:params.max_rows]

            results[rel_type] = {
                "field": bds_field,
                "count": len(rows),
                "data": rows,
            }

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [
                f"## Supply Chain: {params.security}",
                ""
            ]

            if all_errors:
                lines.append(f"**Errors**: {', '.join(all_errors)}")
                lines.append("")

            for rel_type, rel_data in results.items():
                lines.append(f"### {rel_type.title()} ({rel_data['count']})")
                lines.append("")

                rows = rel_data["data"]
                if rows:
                    columns = list(rows[0].keys())
                    lines.append("| " + " | ".join(columns) + " |")
                    lines.append("|" + "---|" * len(columns))
                    for row in rows:
                        vals = []
                        for col in columns:
                            v = row.get(col, "")
                            if isinstance(v, float):
                                v = f"{v:.2f}"
                            val_str = str(v)
                            if len(val_str) > 35:
                                val_str = val_str[:32] + "..."
                            vals.append(val_str)
                        lines.append("| " + " | ".join(vals) + " |")
                    lines.append("")
                else:
                    lines.append("*No data available*")
                    lines.append("")

            result = "\n".join(lines)
        else:
            result = json.dumps({
                "security": params.security,
                "relationships": results,
                "errors": all_errors,
            }, indent=2, default=str)

        return _truncate_response(result)

    except Exception as e:
        logger.exception("Error fetching supply chain data")
        return f"Error fetching supply chain data: {str(e)}"

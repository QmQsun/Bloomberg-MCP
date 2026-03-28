"""Output formatting functions for Bloomberg MCP tool responses."""

import json
from typing import Optional

from .models.enums import ResponseFormat


def _format_security_data(data, response_format: ResponseFormat) -> str:
    """Format SecurityData results."""
    if response_format == ResponseFormat.MARKDOWN:
        lines = []
        for sec in data:
            lines.append(f"## {sec.security}")
            if sec.errors:
                lines.append(f"**Errors**: {', '.join(sec.errors)}")
            for field, value in sec.fields.items():
                lines.append(f"- **{field}**: {value}")
            lines.append("")
        return "\n".join(lines) if lines else "No data returned."
    else:
        return json.dumps([{
            "security": sec.security,
            "fields": sec.fields,
            "errors": sec.errors
        } for sec in data], indent=2, default=str)


def _format_historical_data(data, response_format: ResponseFormat) -> str:
    """Format HistoricalData results."""
    if response_format == ResponseFormat.MARKDOWN:
        lines = []
        for hist in data:
            lines.append(f"## {hist.security}")
            if hist.errors:
                lines.append(f"**Errors**: {', '.join(hist.errors)}")
            lines.append(f"**Data points**: {len(hist.data)}")
            if hist.data:
                lines.append("\n| Date | " + " | ".join(k for k in hist.data[0].keys() if k != "date") + " |")
                lines.append("|---" * (len(hist.data[0])) + "|")
                for row in hist.data[:50]:  # Limit rows in markdown
                    date_str = row.get("date", "")
                    if hasattr(date_str, "strftime"):
                        date_str = date_str.strftime("%Y-%m-%d")
                    values = [str(v) for k, v in row.items() if k != "date"]
                    lines.append(f"| {date_str} | " + " | ".join(values) + " |")
                if len(hist.data) > 50:
                    lines.append(f"\n*... and {len(hist.data) - 50} more rows*")
            lines.append("")
        return "\n".join(lines) if lines else "No data returned."
    else:
        return json.dumps([{
            "security": hist.security,
            "data": hist.data,
            "errors": hist.errors
        } for hist in data], indent=2, default=str)


def _format_screen_result(result, response_format: ResponseFormat, max_results: Optional[int] = None) -> str:
    """Format ScreenResult for output."""
    # Limit results if requested
    securities = result.securities
    field_data = result.field_data
    if max_results:
        securities = securities[:max_results]
        field_data = field_data[:max_results]

    if response_format == ResponseFormat.MARKDOWN:
        lines = [
            f"## Screen: {result.screen_name}",
            f"**Securities found**: {len(result.securities)}" + (f" (showing {len(securities)})" if max_results else ""),
            ""
        ]

        if result.errors:
            lines.append(f"**Errors**: {', '.join(result.errors)}")
            lines.append("")

        if result.columns:
            lines.append(f"**Columns**: {', '.join(result.columns)}")
            lines.append("")

        # Create table if we have field data
        if field_data:
            # Determine columns to show (limit width)
            show_cols = ["security"] + [c for c in result.columns if c != "Ticker"][:5]
            lines.append("| " + " | ".join(show_cols) + " |")
            lines.append("|" + "---|" * len(show_cols))

            for row in field_data[:100]:
                values = []
                for col in show_cols:
                    val = row.get(col, "")
                    if isinstance(val, float):
                        val = f"{val:.2f}"
                    values.append(str(val)[:20])
                lines.append("| " + " | ".join(values) + " |")

            if len(field_data) > 100:
                lines.append(f"\n*... and {len(field_data) - 100} more rows*")

        return "\n".join(lines)
    else:
        return json.dumps({
            "screen_name": result.screen_name,
            "total_securities": len(result.securities),
            "securities": securities,
            "field_data": field_data,
            "columns": result.columns,
            "errors": result.errors
        }, indent=2, default=str)

"""Output formatting functions for Bloomberg MCP tool responses."""

import json
from typing import List, Optional

from .models.enums import ResponseFormat
from .utils import CHARACTER_LIMIT


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


# ============================================================================
# Smart truncation — structure-aware, preserves summary for large results
# ============================================================================

def _smart_truncate_security_data(
    data: list,
    formatted: str,
    char_limit: int = CHARACTER_LIMIT,
) -> str:
    """Truncate BDP output with a summary header when it exceeds char_limit.

    Instead of cutting mid-text, shows a summary of all securities
    followed by full data for as many securities as fit.
    """
    if len(formatted) <= char_limit:
        return formatted

    total = len(data)
    with_data = sum(1 for s in data if s.fields)
    with_errors = sum(1 for s in data if s.errors)
    field_count = len(data[0].fields) if data and data[0].fields else 0

    summary_lines = [
        "## Response Summary (truncated)",
        f"**Total securities**: {total} | **With data**: {with_data} | "
        f"**With errors**: {with_errors} | **Fields**: {field_count}",
        "",
    ]

    # Add a compact snapshot table: one row per security, key fields only
    # Pick up to 3 representative fields to show
    if data and data[0].fields:
        all_field_names = list(data[0].fields.keys())
        # Prioritize price/valuation fields for the summary
        priority = ["PX_LAST", "CUR_MKT_CAP", "PE_RATIO", "CHG_PCT_1D", "VOLUME"]
        show_fields = [f for f in priority if f in all_field_names][:3]
        if not show_fields:
            show_fields = all_field_names[:3]

        summary_lines.append("| Security | " + " | ".join(show_fields) + " |")
        summary_lines.append("|---" + "|---" * len(show_fields) + "|")

        for sec in data:
            vals = []
            for f in show_fields:
                v = sec.fields.get(f, "")
                if isinstance(v, float):
                    v = f"{v:,.2f}"
                vals.append(str(v)[:15])
            summary_lines.append(f"| {sec.security} | " + " | ".join(vals) + " |")

        summary_lines.append("")

    summary = "\n".join(summary_lines)

    # If even the summary exceeds limit, truncate the summary table
    if len(summary) > char_limit:
        # Keep header + first N rows of summary that fit
        return summary[:char_limit - 100] + "\n\n... Summary truncated."

    # Fill remaining budget with full detail for first N securities
    remaining = char_limit - len(summary) - 200  # buffer
    summary_lines.append("---")
    summary_lines.append(f"**Full detail (first securities, {remaining:,} char budget):**\n")

    detail_lines = []
    char_used = 0
    shown = 0
    for sec in data:
        block = f"## {sec.security}\n"
        for field_name, value in sec.fields.items():
            block += f"- **{field_name}**: {value}\n"
        block += "\n"

        if char_used + len(block) > remaining:
            break
        detail_lines.append(block)
        char_used += len(block)
        shown += 1

    summary_lines.extend(detail_lines)
    if shown < total:
        summary_lines.append(f"\n*... {total - shown} more securities not shown*")

    return "\n".join(summary_lines)


def _smart_truncate_historical_data(
    data: list,
    formatted: str,
    char_limit: int = CHARACTER_LIMIT,
) -> str:
    """Truncate BDH output with a summary header when it exceeds char_limit.

    Shows per-security stats (date range, latest value, point count) for ALL
    securities, then full time series for as many securities as fit.
    """
    if len(formatted) <= char_limit:
        return formatted

    total = len(data)
    total_rows = sum(len(h.data) for h in data)
    with_data = sum(1 for h in data if h.data)
    with_errors = sum(1 for h in data if h.errors)

    # Determine field names from first security with data
    field_names = []
    for h in data:
        if h.data:
            field_names = [k for k in h.data[0].keys() if k != "date"]
            break

    # Date range
    first_date = last_date = ""
    for h in data:
        if h.data:
            d = h.data[0].get("date", "")
            first_date = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            d = h.data[-1].get("date", "")
            last_date = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            break

    summary_lines = [
        "## Response Summary (truncated)",
        f"**Securities**: {total} | **With data**: {with_data} | "
        f"**With errors**: {with_errors}",
        f"**Total data points**: {total_rows:,} | **Fields**: {', '.join(field_names)}",
        f"**Date range**: {first_date} to {last_date}",
        "",
    ]

    # Per-security snapshot table — show latest values
    # Pick first field (usually PX_LAST) for the summary column
    show_field = field_names[0] if field_names else None

    summary_lines.append("| Security | Points | First | Last | "
                         + (f"{show_field} (latest)" if show_field else "Status") + " |")
    summary_lines.append("|---|---|---|---|---|")

    for h in data:
        if h.data:
            pts = len(h.data)
            fd = h.data[0].get("date", "")
            ld = h.data[-1].get("date", "")
            fd_str = fd.strftime("%Y-%m-%d") if hasattr(fd, "strftime") else str(fd)
            ld_str = ld.strftime("%Y-%m-%d") if hasattr(ld, "strftime") else str(ld)
            last_val = h.data[-1].get(show_field, "") if show_field else ""
            if isinstance(last_val, float):
                last_val = f"{last_val:,.2f}"
            summary_lines.append(
                f"| {h.security} | {pts} | {fd_str} | {ld_str} | {last_val} |"
            )
        else:
            err = h.errors[0][:40] if h.errors else "no data"
            summary_lines.append(f"| {h.security} | 0 | — | — | {err} |")

    summary_lines.append("")
    summary = "\n".join(summary_lines)

    # If the summary table itself is too big, cap at ~200 securities
    if len(summary) > char_limit:
        summary_lines_truncated = summary_lines[:10]  # header rows
        for h in data[:200]:
            if h.data:
                pts = len(h.data)
                ld = h.data[-1].get("date", "")
                ld_str = ld.strftime("%Y-%m-%d") if hasattr(ld, "strftime") else str(ld)
                last_val = h.data[-1].get(show_field, "") if show_field else ""
                if isinstance(last_val, float):
                    last_val = f"{last_val:,.2f}"
                summary_lines_truncated.append(
                    f"| {h.security} | {pts} | ... | {ld_str} | {last_val} |"
                )
        if total > 200:
            summary_lines_truncated.append(f"\n*... {total - 200} more securities*")
        return "\n".join(summary_lines_truncated)

    # Fill remaining budget with full time series
    remaining = char_limit - len(summary) - 200
    summary_lines.append("---")
    summary_lines.append(f"**Full time series (first securities, {remaining:,} char budget):**\n")

    shown = 0
    char_used = 0
    for h in data:
        if not h.data:
            continue
        block_lines = [f"### {h.security} ({len(h.data)} points)"]
        # Table header
        cols = [k for k in h.data[0].keys() if k != "date"]
        block_lines.append("| Date | " + " | ".join(cols) + " |")
        block_lines.append("|---" * (len(cols) + 1) + "|")
        for row in h.data:
            d = row.get("date", "")
            d_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            vals = [str(row.get(c, "")) for c in cols]
            block_lines.append(f"| {d_str} | " + " | ".join(vals) + " |")
        block_lines.append("")
        block = "\n".join(block_lines)

        if char_used + len(block) > remaining:
            break
        summary_lines.append(block)
        char_used += len(block)
        shown += 1

    if shown < with_data:
        summary_lines.append(f"\n*... {with_data - shown} more securities with data not shown*")

    return "\n".join(summary_lines)

"""Screening tool handlers: run_screen, get_universe, dynamic_screen."""

import json
import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import RunScreenInput, GetUniverseInput, DynamicScreenInput, ResponseFormat
from bloomberg_mcp.utils import _expand_fields, _truncate_response, _get_fieldset_map
from bloomberg_mcp.formatters import _format_screen_result
from bloomberg_mcp.core.logging import log_tool_call
from bloomberg_mcp.handlers._common import pre_request, fallback_or_error

logger = logging.getLogger(__name__)


@mcp.tool(
    name="bloomberg_run_screen",
    annotations={
        "title": "Run Equity Screen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_run_screen(params: RunScreenInput) -> str:
    """
    Run a pre-saved Bloomberg equity screen (EQS).

    Executes a saved screen from Bloomberg's Equity Screening tool and returns
    the list of matching securities along with any output fields defined in
    the screen.

    Screens must be created and saved in Bloomberg Terminal EQS <GO> before
    they can be accessed via API.

    Args:
        params: RunScreenInput containing screen name, type, and options

    Returns:
        JSON or Markdown formatted list of securities with field data

    Example:
        screen_name="Japan_ADR_Universe", screen_type="PRIVATE"
    """
    with log_tool_call("bloomberg_run_screen") as ctx:
        try:
            pre_request()

            from bloomberg_mcp.tools import run_screen

            result = run_screen(
                screen_name=params.screen_name,
                screen_type=params.screen_type,
                group=params.group
            )

            if result.errors and not result.securities:
                return f"Screen error: {', '.join(result.errors)}"

            formatted = _format_screen_result(result, params.response_format, params.max_results)
            ctx["result_size"] = len(formatted)
            return _truncate_response(formatted)

        except Exception as e:
            ctx["error"] = True
            return fallback_or_error(e, "bloomberg_run_screen")


@mcp.tool(
    name="bloomberg_get_universe",
    annotations={
        "title": "Get Universe Securities",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_universe(params: GetUniverseInput) -> str:
    """
    Get a list of securities from an index or saved Bloomberg screen.

    Use this tool to discover what securities are in a universe BEFORE
    running a dynamic screen. This helps you understand the size and
    composition of different universes.

    UNIVERSE SOURCES:

    INDEX CONSTITUENTS (use "index:" prefix):
    - "index:NKY Index" - Nikkei 225 (~225 Japan large-caps)
    - "index:TPX Index" - TOPIX (~2000 Japan equities)
    - "index:SPX Index" - S&P 500 (~500 US large-caps)
    - "index:NDX Index" - Nasdaq 100 (~100 US tech-heavy)
    - "index:SOX Index" - Philadelphia Semiconductor (~30 semis)
    - "index:RTY Index" - Russell 2000 (~2000 US small-caps)

    SAVED BLOOMBERG SCREENS (use "screen:" prefix):
    - "screen:Japan_Liquid_ADRs" - Pre-saved screen of liquid Japan ADRs
    - "screen:YourScreenName" - Any screen saved in EQS <GO>

    Args:
        params: GetUniverseInput with source, optional include_fields, and max_results

    Returns:
        JSON list of security identifiers (or with field data if include_fields specified)

    Example:
        source="index:SOX Index" -> Returns ~30 semiconductor stocks
        source="index:SOX Index", include_fields=["PX_LAST", "CHG_PCT_1D"] -> With price data
        source="index:SOX Index", include_fields=["PRICE", "MOMENTUM"] -> FieldSet shortcuts
    """
    with log_tool_call("bloomberg_get_universe") as ctx:
        try:
            pre_request()

            from bloomberg_mcp.tools.dynamic_screening.custom_eqs import (
                get_universe_from_screen,
                get_index_constituents,
            )

            source = params.source.strip()
            securities = []

            if source.lower().startswith("index:"):
                index_ticker = source[6:].strip()
                securities = get_index_constituents(index_ticker)
            elif source.lower().startswith("screen:"):
                screen_name = source[7:].strip()
                securities = get_universe_from_screen(screen_name)
            else:
                return f"Error: Invalid source format. Use 'index:TICKER' or 'screen:NAME'. Got: {source}"

            if params.max_results and len(securities) > params.max_results:
                securities = securities[:params.max_results]
                truncated = True
            else:
                truncated = False

            field_data = None
            if params.include_fields:
                from bloomberg_mcp.tools import get_reference_data

                expanded_fields = _expand_fields(params.include_fields)
                ref_data = get_reference_data(
                    securities=securities,
                    fields=expanded_fields
                )
                field_data = [
                    {"security": d.security, **d.fields}
                    for d in ref_data
                ]

            result = {
                "source": source,
                "count": len(securities),
                "truncated": truncated,
                "securities": securities,
            }

            if field_data:
                result["fields_requested"] = _expand_fields(params.include_fields)
                result["data"] = field_data

            output = json.dumps(result, indent=2, default=str)
            ctx["result_size"] = len(output)
            return output

        except Exception as e:
            ctx["error"] = True
            return fallback_or_error(e, "bloomberg_get_universe")


@mcp.tool(
    name="bloomberg_dynamic_screen",
    annotations={
        "title": "Run Dynamic Screen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_dynamic_screen(params: DynamicScreenInput) -> str:
    """
    Run a dynamic equity screen with custom universe, fields, filters, and ranking.

    This is the primary tool for LLM-driven market analysis. You can:
    1. Choose ANY universe (index, saved screen, or explicit list)
    2. Fetch any combination of Bloomberg fields
    3. Apply filters to narrow results
    4. Rank and select top/bottom N securities

    UNIVERSE OPTIONS:

    Use a string with prefix:
    - "index:SPX Index" - S&P 500 constituents (~500)
    - "index:NKY Index" - Nikkei 225 (~225)
    - "index:SOX Index" - Semiconductor Index (~30)
    - "screen:Japan_Liquid_ADRs" - Saved Bloomberg screen

    Or provide an explicit list:
    - ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity"]

    FIELDSET SHORTCUTS (expand to multiple fields):

    - "RVOL" -> VOLUME, VOLUME_AVG_20D, TURNOVER (+ computed rvol)
    - "MOMENTUM" -> CHG_PCT_1D, CHG_PCT_5D, CHG_PCT_1M, CHG_PCT_YTD
    - "MOMENTUM_EXTENDED" -> adds CHG_PCT_3M, CHG_PCT_6M, CHG_PCT_1YR
    - "SENTIMENT" -> NEWS_SENTIMENT, NEWS_SENTIMENT_DAILY_AVG
    - "SECTOR" -> GICS_SECTOR_NAME, GICS_INDUSTRY_GROUP_NAME, GICS_INDUSTRY_NAME
    - "TECHNICAL" -> RSI_14D, VOLATILITY_30D, VOLATILITY_90D, BETA_RAW_OVERRIDABLE
    - "VALUATION" -> PE_RATIO, PX_TO_BOOK_RATIO, CUR_MKT_CAP, DIVIDEND_YIELD
    - "PRICE" -> PX_LAST, PX_OPEN, PX_HIGH, PX_LOW, CHG_PCT_1D
    - "ADR" -> PX_LAST, CHG_PCT_1D, VOLUME, VOLUME_AVG_20D, NEWS_SENTIMENT, GICS_SECTOR_NAME
    - "MORNING_NOTE" -> Comprehensive set for morning analysis

    You can also use raw Bloomberg fields: "PX_LAST", "PE_RATIO", etc.

    FILTER OPERATORS:

    - "gt": greater than (e.g., rvol > 2.0)
    - "gte": greater than or equal
    - "lt": less than
    - "lte": less than or equal
    - "eq": equals (for strings like sector names)
    - "neq": not equals
    - "between": range [min, max] inclusive
    - "in": value in list (for multiple sectors)

    FILTER EXAMPLES:

    {"field": "rvol", "op": "gt", "value": 1.5}
    {"field": "CHG_PCT_1D", "op": "gt", "value": 2.0}
    {"field": "GICS_SECTOR_NAME", "op": "eq", "value": "Information Technology"}
    {"field": "CHG_PCT_1D", "op": "between", "value": [-5, 5]}
    {"field": "GICS_SECTOR_NAME", "op": "in", "value": ["Financials", "Industrials"]}

    RANKING:

    Use rank_by to sort results by any field (rvol, CHG_PCT_1D, NEWS_SENTIMENT, etc.)
    Combined with top_n to get the top N results.

    SCREENING TIPS:

    1. For small universes (<50), prefer ranking over strict filters
    2. Use broader filters first, then narrow down
    3. Combine FieldSets: ["RVOL", "MOMENTUM", "SECTOR"]
    4. The "rvol" field is computed as VOLUME/VOLUME_AVG_20D

    Args:
        params: DynamicScreenInput with universe, fields, filters, ranking

    Returns:
        JSON with screen results including securities, fields, and metadata

    Example:
        name="High RVOL Tech Stocks"
        universe="index:SOX Index"
        fields=["RVOL", "MOMENTUM", "SECTOR"]
        filters=[{"field": "rvol", "op": "gt", "value": 1.5}]
        rank_by="rvol"
        top_n=10
    """
    with log_tool_call("bloomberg_dynamic_screen") as ctx:
        try:
            pre_request()

            from bloomberg_mcp.tools.dynamic_screening import (
                DynamicScreen,
                FieldSets,
            )
            from bloomberg_mcp.tools.dynamic_screening.filters import (
                ComparisonFilter,
                BetweenFilter,
                InFilter,
            )

            screen = DynamicScreen(params.name)

            # Configure universe
            universe = params.universe
            if isinstance(universe, str):
                universe = universe.strip()
                if universe.lower().startswith("index:"):
                    index_ticker = universe[6:].strip()
                    screen.universe_from_index(index_ticker)
                elif universe.lower().startswith("screen:"):
                    screen_name = universe[7:].strip()
                    screen.universe_from_screen(screen_name)
                else:
                    return f"Error: Invalid universe format. Use 'index:TICKER', 'screen:NAME', or a list of securities. Got: {universe}"
            elif isinstance(universe, list):
                screen.universe_from_list(universe)
            else:
                return f"Error: Universe must be a string with prefix or a list of securities. Got: {type(universe)}"

            # Resolve and add fields
            fieldset_map = _get_fieldset_map()

            for field_spec in params.fields:
                field_upper = field_spec.upper()
                if field_upper in fieldset_map:
                    screen.with_fields(fieldset_map[field_upper])
                else:
                    screen.with_fields([field_spec])

            # Apply filters
            if params.filters:
                for f in params.filters:
                    op = f.op.lower()
                    field = f.field
                    value = f.value

                    if op == "gt":
                        screen.filter(ComparisonFilter(field, "gt", value))
                    elif op == "gte":
                        screen.filter(ComparisonFilter(field, "gte", value))
                    elif op == "lt":
                        screen.filter(ComparisonFilter(field, "lt", value))
                    elif op == "lte":
                        screen.filter(ComparisonFilter(field, "lte", value))
                    elif op == "eq":
                        screen.filter(ComparisonFilter(field, "eq", value))
                    elif op in ("neq", "ne"):
                        screen.filter(ComparisonFilter(field, "ne", value))
                    elif op == "between":
                        if isinstance(value, list) and len(value) == 2:
                            screen.filter(BetweenFilter(field, value[0], value[1]))
                        else:
                            return f"Error: 'between' filter requires [min, max] list. Got: {value}"
                    elif op == "in":
                        if isinstance(value, list):
                            screen.filter(InFilter(field, value))
                        else:
                            return f"Error: 'in' filter requires a list of values. Got: {value}"
                    else:
                        return f"Error: Unknown filter operator '{op}'. Valid: gt, gte, lt, lte, eq, neq, between, in"

            # Apply ranking
            if params.rank_by:
                screen.rank_by(params.rank_by, descending=params.rank_descending)
                screen.top(params.top_n)

            # Execute screen
            result = screen.run()

            # Format output
            if params.response_format == ResponseFormat.MARKDOWN:
                lines = [
                    f"## Screen: {result.name}",
                    f"**Universe**: {result.universe_source} ({result.universe_size} securities)",
                    f"**Passed filters**: {result.filtered_count}",
                    f"**Execution time**: {result.execution_time_ms:.0f}ms",
                    ""
                ]

                if result.errors:
                    lines.append(f"**Errors**: {', '.join(result.errors)}")
                    lines.append("")

                if result.filters_applied:
                    lines.append(f"**Filters**: {', '.join(result.filters_applied)}")
                    lines.append("")

                if result.records:
                    lines.append("| Rank | Security | Price | Chg% | RVOL | Sector |")
                    lines.append("|------|----------|-------|------|------|--------|")

                    for rec in result.records[:50]:
                        rank = rec.rank or "-"
                        price = f"${rec.price:.2f}" if rec.price else "-"
                        chg = f"{rec.change_pct:+.2f}%" if rec.change_pct else "-"
                        rvol = f"{rec.rvol:.2f}x" if rec.rvol else "-"
                        sector = rec.sector[:15] if rec.sector else "-"
                        lines.append(f"| {rank} | {rec.ticker} | {price} | {chg} | {rvol} | {sector} |")

                    if len(result.records) > 50:
                        lines.append(f"\n*... and {len(result.records) - 50} more*")

                output = "\n".join(lines)
            else:
                output = json.dumps(result.to_dict(), indent=2, default=str)

            ctx["result_size"] = len(output)
            return output

        except Exception as e:
            ctx["error"] = True
            logger.exception("Error running dynamic screen")
            return fallback_or_error(e, "bloomberg_dynamic_screen")

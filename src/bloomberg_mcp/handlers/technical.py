"""Technical analysis tool handler (//blp/tasvc)."""

import json
import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import TechnicalAnalysisInput, ResponseFormat
from bloomberg_mcp.utils import _truncate_response

logger = logging.getLogger(__name__)


@mcp.tool(
    name="bloomberg_get_technical_analysis",
    annotations={
        "title": "Get Technical Analysis",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_technical_analysis(params: TechnicalAnalysisInput) -> str:
    """
    Get technical indicators via Bloomberg TA service (//blp/tasvc).

    Computes technical studies on historical price data for a single security.

    SUPPORTED STUDIES:
    - rsi: Relative Strength Index (default period: 14)
    - macd: Moving Average Convergence Divergence (12/26/9)
    - sma: Simple Moving Average (default period: 20)
    - ema: Exponential Moving Average (default period: 20)
    - bollinger: Bollinger Bands (default period: 20, 2 std dev)
    - dmi: Directional Movement Index / ADX (default period: 14)
    - stochastic: Stochastic Oscillator (default period: 14)

    Args:
        params: TechnicalAnalysisInput with security, study, date range, period

    Returns:
        JSON or Markdown formatted time series of technical indicator values

    Example:
        security="AAPL US Equity", study="rsi", start_date="20240101",
        end_date="20240630", period=14
    """
    try:
        from bloomberg_mcp.core.session import BloombergSession
        from bloomberg_mcp.core.requests import build_study_request
        from bloomberg_mcp.core.responses import parse_study_response
        from bloomberg_mcp.utils import BLOOMBERG_HOST, BLOOMBERG_PORT

        # Get session
        session = BloombergSession.get_instance(host=BLOOMBERG_HOST, port=BLOOMBERG_PORT)
        if not session.is_connected():
            if not session.connect():
                return "Error: Failed to connect to Bloomberg Terminal."

        # Open tasvc service
        service = session.get_service("//blp/tasvc")
        if service is None:
            return (
                "Error: Failed to open //blp/tasvc service. "
                "Technical analysis service may not be available on this terminal."
            )

        # Build and send request
        request = build_study_request(
            service=service,
            security=params.security,
            study=params.study,
            start_date=params.start_date,
            end_date=params.end_date,
            period=params.period,
        )

        data_points = session.send_request(
            request,
            service_name="//blp/tasvc",
            parse_func=parse_study_response,
        )

        if not data_points:
            return f"No technical analysis data returned for {params.security} / {params.study}"

        # Build display name
        period_str = f"({params.period})" if params.period else ""
        study_label = f"{params.study.upper()}{period_str}"

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [
                f"## Technical Analysis: {params.security}",
                f"**Study**: {study_label}",
                f"**Range**: {params.start_date} to {params.end_date}",
                f"**Data points**: {len(data_points)}",
                ""
            ]

            # Determine column names from first data point
            if data_points:
                value_keys = list(data_points[0].values.keys())
                cols = ["Date"] + value_keys
                lines.append("| " + " | ".join(cols) + " |")
                lines.append("|" + "---|" * len(cols))

                for dp in data_points[:100]:
                    date_str = str(dp.date)
                    if hasattr(dp.date, "strftime"):
                        date_str = dp.date.strftime("%Y-%m-%d")
                    row = [date_str]
                    for k in value_keys:
                        v = dp.values.get(k)
                        if isinstance(v, float):
                            row.append(f"{v:.4f}")
                        else:
                            row.append(str(v) if v is not None else "-")
                    lines.append("| " + " | ".join(row) + " |")

                if len(data_points) > 100:
                    lines.append(f"\n*... and {len(data_points) - 100} more data points*")

            result = "\n".join(lines)
        else:
            result = json.dumps({
                "security": params.security,
                "study": study_label,
                "start_date": params.start_date,
                "end_date": params.end_date,
                "total_points": len(data_points),
                "data": [
                    {"date": str(dp.date), **dp.values}
                    for dp in data_points
                ],
            }, indent=2, default=str)

        return _truncate_response(result)

    except Exception as e:
        logger.exception("Error fetching technical analysis")
        return f"Error fetching technical analysis: {str(e)}"

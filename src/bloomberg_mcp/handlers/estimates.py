"""Multi-period consensus estimates tool handler."""

import json
import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import EstimatesDetailInput, ResponseFormat
from bloomberg_mcp.utils import _truncate_response

logger = logging.getLogger(__name__)

# Bloomberg field templates for estimates.
# For each metric (e.g., EPS), fields become BEST_EPS, BEST_EPS_MEDIAN, etc.
ESTIMATE_FIELD_TEMPLATES = {
    "EPS":        ("BEST_EPS", "BEST_EPS_MEDIAN", "BEST_EPS_HIGH", "BEST_EPS_LOW",
                   "BEST_EPS_NUM_EST"),
    "SALES":      ("BEST_SALES", "BEST_SALES_MEDIAN", "BEST_SALES_HIGH", "BEST_SALES_LOW",
                   "BEST_SALES_NUM_EST"),
    "EBITDA":     ("BEST_EBITDA", "BEST_EBITDA_MEDIAN", "BEST_EBITDA_HIGH", "BEST_EBITDA_LOW",
                   "BEST_EBITDA_NUM_EST"),
    "NET_INCOME": ("BEST_NET_INCOME", "BEST_NET_INCOME_MEDIAN", "BEST_NET_INCOME_HIGH",
                   "BEST_NET_INCOME_LOW", "BEST_NET_INCOME_NUM_EST"),
    "OPER_INC":   ("BEST_OPER_INC", "BEST_OPER_INC_MEDIAN", "BEST_OPER_INC_HIGH",
                   "BEST_OPER_INC_LOW", "BEST_OPER_INC_NUM_EST"),
    "FCF":        ("BEST_FCF", "BEST_FCF_MEDIAN", "BEST_FCF_HIGH",
                   "BEST_FCF_LOW", "BEST_FCF_NUM_EST"),
}

REVISION_FIELDS = {
    "EPS": "BEST_EPS_4WK_CHG",
    "SALES": "BEST_SALES_4WK_CHG",
    "EBITDA": "BEST_EBITDA_4WK_CHG",
}

SURPRISE_FIELDS = {
    "EPS": "BEST_EPS_SURPRISE",
    "SALES": "BEST_SALES_SURPRISE",
}


@mcp.tool(
    name="bloomberg_get_estimates_detail",
    annotations={
        "title": "Get Estimates Detail",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_estimates_detail(params: EstimatesDetailInput) -> str:
    """
    Get multi-period consensus estimates with revision momentum.

    For each security x period, returns consensus estimates including
    mean, median, high, low, analyst count, 4-week revision, and surprise.

    Uses BEST_FPERIOD_OVERRIDE to fetch different fiscal periods.

    METRICS: EPS, SALES, EBITDA, NET_INCOME, OPER_INC, FCF

    PERIODS:
    - 1FY/2FY/3FY: Current/next/next+1 fiscal year
    - 1FQ/2FQ/3FQ/4FQ: Current through 4th-next fiscal quarter

    Args:
        params: EstimatesDetailInput with securities, metrics, periods

    Returns:
        JSON or Markdown with multi-period consensus data

    Example:
        securities=["AAPL US Equity"], metrics=["EPS", "SALES"],
        periods=["1FY", "2FY", "1FQ"]
    """
    try:
        from bloomberg_mcp.tools import get_reference_data

        # Build field list for each metric
        fields = []
        for metric_key in params.metrics:
            metric_upper = metric_key.upper()
            if metric_upper in ESTIMATE_FIELD_TEMPLATES:
                fields.extend(ESTIMATE_FIELD_TEMPLATES[metric_upper])
            if params.include_revisions and metric_upper in REVISION_FIELDS:
                fields.append(REVISION_FIELDS[metric_upper])
            if params.include_surprise and metric_upper in SURPRISE_FIELDS:
                fields.append(SURPRISE_FIELDS[metric_upper])

        # Deduplicate
        fields = list(dict.fromkeys(fields))

        # Fetch data for each period using BEST_FPERIOD_OVERRIDE
        all_results = {}
        for security in params.securities:
            all_results[security] = {}

        for period in params.periods:
            overrides = {"BEST_FPERIOD_OVERRIDE": period}

            data = get_reference_data(
                securities=params.securities,
                fields=fields,
                overrides=overrides
            )

            for sec_data in data:
                if sec_data.security not in all_results:
                    all_results[sec_data.security] = {}
                all_results[sec_data.security][period] = {
                    "fields": sec_data.fields,
                    "errors": sec_data.errors,
                }

        # Format output
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = ["## Consensus Estimates Detail", ""]

            for security, periods_data in all_results.items():
                lines.append(f"### {security}")
                lines.append("")

                for metric_key in params.metrics:
                    metric_upper = metric_key.upper()
                    base_field = f"BEST_{metric_upper}"
                    lines.append(f"**{metric_upper} Estimates:**")
                    lines.append("")

                    # Table header
                    cols = ["Period", "Consensus", "Median", "High", "Low", "#Analysts"]
                    if params.include_revisions and metric_upper in REVISION_FIELDS:
                        cols.append("4Wk Rev")
                    lines.append("| " + " | ".join(cols) + " |")
                    lines.append("|" + "---|" * len(cols))

                    for period, pdata in periods_data.items():
                        f = pdata["fields"]
                        row = [
                            period,
                            _fmt(f.get(base_field)),
                            _fmt(f.get(f"{base_field}_MEDIAN")),
                            _fmt(f.get(f"{base_field}_HIGH")),
                            _fmt(f.get(f"{base_field}_LOW")),
                            _fmt(f.get(f"{base_field}_NUM_EST")),
                        ]
                        if params.include_revisions and metric_upper in REVISION_FIELDS:
                            rev = f.get(REVISION_FIELDS[metric_upper])
                            row.append(f"{rev:+.2f}%" if isinstance(rev, (int, float)) else "-")
                        lines.append("| " + " | ".join(row) + " |")

                    lines.append("")

                # Surprise section (period-independent, just show once)
                if params.include_surprise:
                    first_period = next(iter(periods_data.values()), {})
                    f = first_period.get("fields", {})
                    surprise_items = []
                    for metric_key2 in params.metrics:
                        mu = metric_key2.upper()
                        if mu in SURPRISE_FIELDS:
                            val = f.get(SURPRISE_FIELDS[mu])
                            if val is not None:
                                surprise_items.append(f"{mu}: {val:+.4f}" if isinstance(val, float) else f"{mu}: {val}")
                    if surprise_items:
                        lines.append(f"**Last Surprise:** {', '.join(surprise_items)}")
                        lines.append("")

            result = "\n".join(lines)
        else:
            result = json.dumps({
                "securities": all_results,
                "metrics": params.metrics,
                "periods": params.periods,
            }, indent=2, default=str)

        return _truncate_response(result)

    except Exception as e:
        logger.exception("Error fetching estimates detail")
        return f"Error fetching estimates detail: {str(e)}"


def _fmt(val) -> str:
    """Format a value for table display."""
    if val is None:
        return "-"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)

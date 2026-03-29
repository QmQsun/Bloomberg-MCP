"""Test 30-day earnings window. Requires live Bloomberg connection."""
import pytest
from datetime import timedelta
from bloomberg_mcp.tools.earnings_calendar import (
    get_earnings_calendar, format_earnings_for_morning_note,
    EarningsCalendarInput, EarningsMode
)


pytestmark = pytest.mark.skipif(
    not pytest.importorskip("os").environ.get("BLOOMBERG_LIVE"),
    reason="Requires live Bloomberg connection (set BLOOMBERG_LIVE=1 to run)",
)


@pytest.fixture
def earnings_params():
    return EarningsCalendarInput(
        mode=EarningsMode.WEEK_AHEAD,
        universe='MORNING_NOTE',
        days_ahead=30,
    )


def test_30day_earnings_window(earnings_params):
    """Verify 30-day earnings calendar returns valid data."""
    result = get_earnings_calendar(earnings_params)
    end_date = result.query_date + timedelta(days=30)

    assert result.query_date is not None
    assert end_date > result.query_date
    assert isinstance(result.reports_this_week, list)


def test_30day_earnings_format(earnings_params):
    """Verify morning note formatting works for 30-day window."""
    result = get_earnings_calendar(earnings_params)
    output = format_earnings_for_morning_note(result)

    assert isinstance(output, str)
    assert len(output) > 0

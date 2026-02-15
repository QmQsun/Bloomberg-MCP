"""Test 30-day earnings window. Requires live Bloomberg connection."""
from datetime import timedelta
from bloomberg_mcp.tools.earnings_calendar import (
    get_earnings_calendar, format_earnings_for_morning_note,
    EarningsCalendarInput, EarningsMode
)

params = EarningsCalendarInput(
    mode=EarningsMode.WEEK_AHEAD,
    universe='MORNING_NOTE',
    days_ahead=30,
)

result = get_earnings_calendar(params)
end_date = result.query_date + timedelta(days=30)
print(f'Query: {result.query_date} to {end_date}')
print(f'Reports this week: {len(result.reports_this_week)}')

for event in result.reports_this_week:
    eps = f'EPS ${event.eps_estimate:.2f}' if event.eps_estimate else ''
    print(f'  {event.report_date} | {event.name} ({event.ticker}) | {eps}')

print()
print('=== Morning Note Format ===')
print(format_earnings_for_morning_note(result))

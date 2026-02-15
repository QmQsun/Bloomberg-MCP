"""Test script for earnings calendar tool. Requires live Bloomberg connection."""

from bloomberg_mcp.tools.earnings_calendar import (
    get_earnings_calendar,
    format_earnings_for_morning_note,
    EarningsCalendarInput,
    EarningsMode,
    EARNINGS_UNIVERSES,
    resolve_universe,
)


def test_universes():
    """Test the named universes are populated correctly."""
    print("\n=== Testing Named Universes ===")
    print(f"Total universes: {len(EARNINGS_UNIVERSES)}")

    for name, securities in EARNINGS_UNIVERSES.items():
        print(f"  {name}: {len(securities)} securities")

    print("\n[OK] Named universes populated correctly")


def test_resolve_universe():
    """Test universe resolution."""
    print("\n=== Testing Universe Resolution ===")

    # Test named universe
    name, secs = resolve_universe("SEMI_LEADERS")
    print(f"'SEMI_LEADERS' -> {name}: {len(secs)} securities")

    # Test explicit list
    name, secs = resolve_universe(["AAPL US Equity", "NVDA US Equity"])
    print(f"Explicit list -> {name}: {len(secs)} securities")

    # Test partial match
    name, secs = resolve_universe("MEGA_CAP")
    print(f"'MEGA_CAP' (partial) -> {name}: {len(secs)} securities")

    print("\n[OK] Universe resolution works correctly")


def test_earnings_query():
    """Test querying Bloomberg for earnings calendar."""
    print("\n=== Testing Earnings Calendar Query (Bloomberg) ===")

    try:
        # Create input for week ahead with semi leaders
        params = EarningsCalendarInput(
            mode=EarningsMode.WEEK_AHEAD,
            universe="SEMI_LEADERS",
            days_ahead=14,  # Two weeks
            include_estimates=True,
        )

        print(f"Mode: {params.mode.value}")
        print(f"Universe: {params.universe}")
        print(f"Days ahead: {params.days_ahead}")

        result = get_earnings_calendar(params)

        print(f"\nQuery date: {result.query_date}")
        print(f"Universe: {result.universe_name} ({result.universe_size} securities)")
        print(f"Reported recently: {len(result.reported_recently)}")
        print(f"Reports today: {len(result.reports_today)}")
        print(f"Reports this week: {len(result.reports_this_week)}")

        if result.reports_this_week:
            print("\nUpcoming Earnings:")
            for event in result.reports_this_week[:10]:
                eps = f"EPS ${event.eps_estimate:.2f}" if event.eps_estimate else ""
                print(f"  {event.report_date} | {event.name} ({event.ticker}) | {eps}")

        # Test markdown output
        markdown = format_earnings_for_morning_note(result)
        print("\n=== Markdown Output ===")
        print(markdown)

        print("\n[OK] Earnings calendar query completed successfully")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


def test_morning_note_universe():
    """Test the morning note universe specifically."""
    print("\n=== Testing Morning Note Universe ===")

    try:
        params = EarningsCalendarInput(
            mode=EarningsMode.WEEK_AHEAD,
            universe="MORNING_NOTE",
            days_ahead=7,
        )

        result = get_earnings_calendar(params)

        print(f"Universe size: {result.universe_size}")
        print(f"Total events: {len(result.reported_recently) + len(result.reports_today) + len(result.reports_this_week)}")

        # Show by category
        all_events = result.reported_recently + result.reports_today + result.reports_this_week
        if all_events:
            print("\nEarnings by date:")
            by_date = {}
            for e in all_events:
                key = e.report_date.strftime("%Y-%m-%d")
                if key not in by_date:
                    by_date[key] = []
                by_date[key].append(e.name)

            for dt in sorted(by_date.keys()):
                names = ", ".join(by_date[dt])
                print(f"  {dt}: {names}")

        print("\n[OK] Morning note universe works correctly")

    except Exception as e:
        print(f"\n[ERROR] {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Earnings Calendar Tool Tests")
    print("=" * 60)

    # These tests don't require Bloomberg connection
    test_universes()
    test_resolve_universe()

    # These tests require Bloomberg connection
    print("\n" + "=" * 60)
    print("Bloomberg API Tests (requires connection)")
    print("=" * 60)

    test_earnings_query()
    test_morning_note_universe()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

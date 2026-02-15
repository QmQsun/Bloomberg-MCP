"""Test script for economic calendar tool. Requires live Bloomberg connection."""

from bloomberg_mcp.tools.economic_calendar import (
    get_economic_calendar,
    format_calendar_for_morning_note,
    EconomicCalendarInput,
    CalendarMode,
    EventImportance,
    INDICATOR_REGISTRY,
    get_indicators_by_filter,
)


def test_indicator_registry():
    """Test the indicator registry is populated correctly."""
    print("\n=== Testing Indicator Registry ===")
    print(f"Total indicators: {len(INDICATOR_REGISTRY)}")

    # Count by region
    regions = {}
    for ticker, meta in INDICATOR_REGISTRY.items():
        regions[meta.region] = regions.get(meta.region, 0) + 1

    print("\nBy region:")
    for region, count in sorted(regions.items()):
        print(f"  {region}: {count}")

    # Count by importance
    importance = {}
    for ticker, meta in INDICATOR_REGISTRY.items():
        importance[meta.importance.value] = importance.get(meta.importance.value, 0) + 1

    print("\nBy importance:")
    for imp, count in sorted(importance.items()):
        print(f"  {imp}: {count}")

    print("\n[OK] Indicator registry populated correctly")


def test_filter():
    """Test the indicator filter function."""
    print("\n=== Testing Indicator Filter ===")

    # Test US high importance
    us_high = get_indicators_by_filter(
        regions=["US"],
        importance=EventImportance.HIGH,
    )
    print(f"\nUS High Importance: {len(us_high)} indicators")
    for ind in us_high[:5]:
        print(f"  - {ind.short_name} ({ind.ticker})")

    # Test Japan central bank
    jp_cb = get_indicators_by_filter(
        regions=["Japan"],
        categories=["central_bank"],
    )
    print(f"\nJapan Central Bank: {len(jp_cb)} indicators")
    for ind in jp_cb:
        print(f"  - {ind.short_name} ({ind.ticker})")

    print("\n[OK] Filter function works correctly")


def test_calendar_query():
    """Test querying Bloomberg for economic calendar."""
    print("\n=== Testing Calendar Query (Bloomberg) ===")

    try:
        # Create input for week ahead
        params = EconomicCalendarInput(
            mode=CalendarMode.WEEK_AHEAD,
            regions=["US", "Japan"],
            importance=EventImportance.HIGH,
            days_ahead=14,  # Two weeks to increase chance of finding events
        )

        print(f"Mode: {params.mode.value}")
        print(f"Regions: {params.regions}")
        print(f"Importance: {params.importance.value}")
        print(f"Days ahead: {params.days_ahead}")

        result = get_economic_calendar(params)

        print(f"\nQuery date: {result.query_date}")
        print(f"Date range: {result.date_range_start} to {result.date_range_end}")
        print(f"Total events: {result.total_events}")

        if result.events:
            print("\nUpcoming Events:")
            for event in result.events[:10]:
                print(f"  {event.release_date} | {event.short_name} ({event.region}) | Prior: {event.prior_value}{event.unit}")
        else:
            print("\nNo events found in date range (this is expected if no releases scheduled)")

        # Test markdown output
        markdown = format_calendar_for_morning_note(result)
        print("\n=== Markdown Output ===")
        print(markdown[:1000] if len(markdown) > 1000 else markdown)

        print("\n[OK] Calendar query completed successfully")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


def test_central_bank_mode():
    """Test central bank mode specifically."""
    print("\n=== Testing Central Bank Mode ===")

    try:
        params = EconomicCalendarInput(
            mode=CalendarMode.CENTRAL_BANK,
            regions=["US", "Japan", "Europe"],
            importance=EventImportance.ALL,  # All importance levels
        )

        result = get_economic_calendar(params)

        print(f"Date range: {result.date_range_start} to {result.date_range_end}")
        print(f"Central bank events: {result.total_events}")

        if result.events:
            for event in result.events:
                print(f"  {event.release_date} | {event.short_name} ({event.region})")

        print("\n[OK] Central bank mode works correctly")

    except Exception as e:
        print(f"\n[ERROR] {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Economic Calendar Tool Tests")
    print("=" * 60)

    # These tests don't require Bloomberg connection
    test_indicator_registry()
    test_filter()

    # This test requires Bloomberg connection
    print("\n" + "=" * 60)
    print("Bloomberg API Tests (requires connection)")
    print("=" * 60)

    test_calendar_query()
    test_central_bank_mode()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

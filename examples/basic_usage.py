"""Basic usage examples for bloomberg-mcp.

All functions auto-connect to Bloomberg - no manual session management needed.
"""

from bloomberg_mcp.tools import (
    get_reference_data,
    get_historical_data,
    get_intraday_bars,
    search_securities,
    search_fields,
)


def example_reference_data():
    """Get current field values for securities."""
    print("\n=== Reference Data ===")

    data = get_reference_data(
        securities=["AAPL US Equity", "MSFT US Equity"],
        fields=["PX_LAST", "PE_RATIO", "DIVIDEND_YIELD", "NAME"]
    )

    for sec in data:
        print(f"\n{sec.security}:")
        for field, value in sec.fields.items():
            print(f"  {field}: {value}")
        if sec.errors:
            print(f"  Errors: {sec.errors}")


def example_historical_data():
    """Get historical time series data."""
    print("\n=== Historical Data ===")

    data = get_historical_data(
        securities=["SPY US Equity"],
        fields=["PX_LAST", "VOLUME"],
        start_date="20240101",
        end_date="20240131",
        periodicity="DAILY"
    )

    for sec in data:
        print(f"\n{sec.security}: {len(sec.data)} data points")
        if sec.data:
            print(f"  First: {sec.data[0]}")
            print(f"  Last:  {sec.data[-1]}")


def example_intraday_bars():
    """Get intraday OHLCV bar data."""
    from datetime import datetime

    print("\n=== Intraday Bars ===")

    # Times must be in GMT
    bars = get_intraday_bars(
        security="AAPL US Equity",
        start=datetime(2024, 12, 10, 14, 30),  # 9:30 AM ET
        end=datetime(2024, 12, 10, 21, 0),     # 4:00 PM ET
        interval=60,
        event_type="TRADE"
    )

    print(f"\nReceived {len(bars)} bars")
    for bar in bars[:3]:
        print(f"  {bar.time}: O={bar.open:.2f} H={bar.high:.2f} L={bar.low:.2f} C={bar.close:.2f}")


def example_search():
    """Search for securities and fields."""
    print("\n=== Search ===")

    # Search for securities
    securities = search_securities("Apple", max_results=3, yellow_key="Equity")
    print("\nSecurities matching 'Apple':")
    for s in securities:
        print(f"  {s['security']}: {s['description']}")

    # Search for fields
    fields = search_fields("price earnings")
    print("\nFields matching 'price earnings':")
    for f in fields[:5]:
        print(f"  {f.get('id')}: {f.get('description')}")


def example_comprehensive_analysis():
    """Fetch comprehensive analysis data for a stock."""
    print("\n=== Comprehensive Analysis ===")

    # Valuation + Profitability + Risk fields
    fields = [
        # Price
        "PX_LAST", "CHG_PCT_1D",
        # Valuation
        "PE_RATIO", "PX_TO_BOOK_RATIO", "EV_TO_EBITDA",
        # Profitability
        "RETURN_ON_EQUITY", "GROSS_MARGIN", "NET_MARGIN",
        # Risk
        "BETA_RAW_OVERRIDABLE", "VOLATILITY_30D",
        # Analyst
        "EQY_REC_CONS", "BEST_TARGET_PRICE",
    ]

    data = get_reference_data(["AAPL US Equity"], fields)

    if data:
        sec = data[0]
        print(f"\n{sec.security} Analysis:")
        print(f"\n  Price: ${sec.fields.get('PX_LAST')} ({sec.fields.get('CHG_PCT_1D'):+.2f}%)")
        print(f"\n  Valuation:")
        print(f"    P/E: {sec.fields.get('PE_RATIO')}")
        print(f"    P/B: {sec.fields.get('PX_TO_BOOK_RATIO')}")
        print(f"    EV/EBITDA: {sec.fields.get('EV_TO_EBITDA')}")
        print(f"\n  Profitability:")
        print(f"    ROE: {sec.fields.get('RETURN_ON_EQUITY')}%")
        print(f"    Gross Margin: {sec.fields.get('GROSS_MARGIN')}%")
        print(f"    Net Margin: {sec.fields.get('NET_MARGIN')}%")
        print(f"\n  Risk:")
        print(f"    Beta: {sec.fields.get('BETA_RAW_OVERRIDABLE')}")
        print(f"    30D Vol: {sec.fields.get('VOLATILITY_30D')}%")
        print(f"\n  Analyst:")
        print(f"    Consensus: {sec.fields.get('EQY_REC_CONS')}")
        print(f"    Target: ${sec.fields.get('BEST_TARGET_PRICE')}")


if __name__ == "__main__":
    print("Bloomberg MCP - Usage Examples")
    print("=" * 50)
    print("\nRequires active Bloomberg Terminal connection.")
    print("Uncomment examples below to run.\n")

    # example_reference_data()
    # example_historical_data()
    # example_intraday_bars()
    # example_search()
    # example_comprehensive_analysis()

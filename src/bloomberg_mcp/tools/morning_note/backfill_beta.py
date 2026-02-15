"""Backfill beta fields (VIX, Gold, 2Y yield) for existing session snapshots.

This script updates existing session_snapshots rows with:
- vix_close, vix_change_pct
- gold_close, gold_change_pct
- us_2y_yield

Run after applying the 001_beta_schema migration.

Usage:
    python -m bloomberg_mcp.tools.morning_note.backfill_beta
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from .historical import get_db_connection, DEFAULT_DB_PATH
from .config import MACRO_COMMODITIES, MACRO_VOLATILITY, MACRO_RATES


def get_dates_missing_beta_data(db_path: Optional[Path] = None) -> List[str]:
    """Get session dates that are missing VIX/Gold/2Y data."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT session_date
            FROM session_snapshots
            WHERE vix_close IS NULL
               OR gold_close IS NULL
               OR us_2y_yield IS NULL
            ORDER BY session_date
        """)
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def backfill_beta_fields(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Backfill VIX, Gold, and 2Y yield data for session snapshots.

    Args:
        start_date: Start date YYYYMMDD (defaults to earliest missing)
        end_date: End date YYYYMMDD (defaults to latest missing)
        db_path: Database path

    Returns:
        Number of rows updated
    """
    from ..historical import get_historical_data

    # Get dates that need backfilling
    missing_dates = get_dates_missing_beta_data(db_path)

    if not missing_dates:
        print("No dates need backfilling")
        return 0

    print(f"Found {len(missing_dates)} dates missing beta data")
    print(f"Date range: {missing_dates[0]} to {missing_dates[-1]}")

    # Convert to YYYYMMDD format for Bloomberg
    if start_date is None:
        start_date = missing_dates[0].replace("-", "")
    if end_date is None:
        end_date = missing_dates[-1].replace("-", "")

    # Securities to fetch
    securities = [
        MACRO_VOLATILITY["vix"].ticker,      # VIX Index
        MACRO_COMMODITIES["gold"].ticker,    # GC1 Comdty
        MACRO_RATES["us_2y"].ticker,         # USGG2YR Index
    ]

    fields = ["PX_LAST", "CHG_PCT_1D"]

    print(f"Fetching historical data from {start_date} to {end_date}...")
    print(f"Securities: {securities}")

    # Fetch historical data
    hist_data = get_historical_data(
        securities=securities,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        periodicity="DAILY",
    )

    # Organize data by date
    data_by_date: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for sec_data in hist_data:
        ticker = sec_data.security
        for point in sec_data.data:
            date_val = point.get("date")
            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)

            if date_str not in data_by_date:
                data_by_date[date_str] = {}

            data_by_date[date_str][ticker] = {
                "last": point.get("PX_LAST"),
                "change_pct": point.get("CHG_PCT_1D"),
            }

    print(f"Got data for {len(data_by_date)} dates")

    # Update database
    conn = get_db_connection(db_path)
    rows_updated = 0

    try:
        vix_ticker = MACRO_VOLATILITY["vix"].ticker
        gold_ticker = MACRO_COMMODITIES["gold"].ticker
        us2y_ticker = MACRO_RATES["us_2y"].ticker

        for session_date in missing_dates:
            day_data = data_by_date.get(session_date, {})

            vix_data = day_data.get(vix_ticker, {})
            gold_data = day_data.get(gold_ticker, {})
            us2y_data = day_data.get(us2y_ticker, {})

            vix_close = vix_data.get("last")
            vix_change = vix_data.get("change_pct")
            gold_close = gold_data.get("last")
            gold_change = gold_data.get("change_pct")
            us_2y_yield = us2y_data.get("last")

            # Only update if we have at least some data
            if vix_close is not None or gold_close is not None or us_2y_yield is not None:
                conn.execute("""
                    UPDATE session_snapshots
                    SET vix_close = COALESCE(?, vix_close),
                        vix_change_pct = COALESCE(?, vix_change_pct),
                        gold_close = COALESCE(?, gold_close),
                        gold_change_pct = COALESCE(?, gold_change_pct),
                        us_2y_yield = COALESCE(?, us_2y_yield)
                    WHERE session_date = ?
                """, (
                    vix_close, vix_change,
                    gold_close, gold_change,
                    us_2y_yield,
                    session_date,
                ))
                rows_updated += 1

        conn.commit()
        print(f"Updated {rows_updated} rows")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        conn.close()

    return rows_updated


def verify_backfill(db_path: Optional[Path] = None) -> None:
    """Verify backfill completed successfully."""
    conn = get_db_connection(db_path)
    try:
        # Count rows with/without beta data
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN vix_close IS NOT NULL THEN 1 ELSE 0 END) as has_vix,
                SUM(CASE WHEN gold_close IS NOT NULL THEN 1 ELSE 0 END) as has_gold,
                SUM(CASE WHEN us_2y_yield IS NOT NULL THEN 1 ELSE 0 END) as has_2y
            FROM session_snapshots
        """)
        row = cursor.fetchone()

        print("\nBackfill Verification:")
        print(f"  Total snapshots: {row[0]}")
        print(f"  With VIX: {row[1]} ({row[1]/row[0]*100:.1f}%)")
        print(f"  With Gold: {row[2]} ({row[2]/row[0]*100:.1f}%)")
        print(f"  With 2Y: {row[3]} ({row[3]/row[0]*100:.1f}%)")

        # Show sample of recent data
        print("\nRecent snapshots with beta data:")
        cursor = conn.execute("""
            SELECT session_date, spx_change_pct, vix_close, gold_close, us_2y_yield
            FROM session_snapshots
            WHERE vix_close IS NOT NULL
            ORDER BY session_date DESC
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}: SPX {row[1]:+.2f}% | VIX: {row[2]:.1f} | Gold: ${row[3]:.0f} | 2Y: {row[4]:.2f}%")

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill beta fields for session snapshots")
    parser.add_argument("--start", type=str, help="Start date YYYYMMDD")
    parser.add_argument("--end", type=str, help="End date YYYYMMDD")
    parser.add_argument("--verify", action="store_true", help="Only verify, don't backfill")
    parser.add_argument("--db", type=str, help="Custom database path")

    args = parser.parse_args()
    db_path = Path(args.db) if args.db else None

    if args.verify:
        verify_backfill(db_path)
    else:
        rows = backfill_beta_fields(args.start, args.end, db_path)
        print(f"\nBackfill complete: {rows} rows updated")
        verify_backfill(db_path)

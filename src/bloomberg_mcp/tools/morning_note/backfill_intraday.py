"""Backfill intraday fields for existing session snapshots.

This script updates existing session_snapshots rows with:
- intraday_character (trending_up, trending_down, mean_reverting, volatile, normal)
- spx_intraday_range_pct (high-low as % of open)
- volume_vs_20d_avg (relative volume)

Run after applying the 001_beta_schema migration.

Usage:
    python -m bloomberg_mcp.tools.morning_note.backfill_intraday
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .historical import get_db_connection, DEFAULT_DB_PATH


def classify_intraday_character(
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
) -> str:
    """Classify session character based on OHLC.

    Returns: 'trending_up', 'trending_down', 'mean_reverting', 'volatile', 'normal'
    """
    if open_price <= 0:
        return "normal"

    range_pct = (high_price - low_price) / open_price * 100
    body_pct = abs(close_price - open_price) / open_price * 100

    # High range with small body = mean reverting
    if range_pct > 1.5 and body_pct < 0.3:
        return "mean_reverting"

    # High range with large body = trending
    if range_pct > 1.0 and body_pct > 0.5:
        return "trending_up" if close_price > open_price else "trending_down"

    # Very high range = volatile
    if range_pct > 2.0:
        return "volatile"

    return "normal"


def get_dates_missing_intraday_data(db_path: Optional[Path] = None) -> List[str]:
    """Get session dates that are missing intraday data."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT session_date
            FROM session_snapshots
            WHERE intraday_character IS NULL
               OR spx_intraday_range_pct IS NULL
               OR volume_vs_20d_avg IS NULL
            ORDER BY session_date
        """)
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def backfill_intraday_fields(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Backfill intraday character, range, and volume data.

    Args:
        start_date: Start date YYYYMMDD (defaults to earliest missing)
        end_date: End date YYYYMMDD (defaults to latest missing)
        db_path: Database path

    Returns:
        Number of rows updated
    """
    from ..historical import get_historical_data

    # Get dates that need backfilling
    missing_dates = get_dates_missing_intraday_data(db_path)

    if not missing_dates:
        print("No dates need backfilling")
        return 0

    print(f"Found {len(missing_dates)} dates missing intraday data")
    print(f"Date range: {missing_dates[0]} to {missing_dates[-1]}")

    # Convert to YYYYMMDD format for Bloomberg
    if start_date is None:
        start_date = missing_dates[0].replace("-", "")
    if end_date is None:
        end_date = missing_dates[-1].replace("-", "")

    # Fetch SPX OHLC and volume data
    securities = ["SPX Index"]
    fields = ["PX_OPEN", "PX_HIGH", "PX_LOW", "PX_LAST", "VOLUME", "VOLUME_AVG_20D"]

    print(f"Fetching historical data from {start_date} to {end_date}...")
    print(f"Securities: {securities}")
    print(f"Fields: {fields}")

    # Fetch historical data
    hist_data = get_historical_data(
        securities=securities,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        periodicity="DAILY",
    )

    # Organize data by date
    data_by_date: Dict[str, Dict[str, Any]] = {}

    for sec_data in hist_data:
        for point in sec_data.data:
            date_val = point.get("date")
            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)

            data_by_date[date_str] = {
                "open": point.get("PX_OPEN"),
                "high": point.get("PX_HIGH"),
                "low": point.get("PX_LOW"),
                "close": point.get("PX_LAST"),
                "volume": point.get("VOLUME"),
                "volume_avg": point.get("VOLUME_AVG_20D"),
            }

    print(f"Got data for {len(data_by_date)} dates")

    # Update database
    conn = get_db_connection(db_path)
    rows_updated = 0

    try:
        for session_date in missing_dates:
            day_data = data_by_date.get(session_date, {})

            open_price = day_data.get("open")
            high_price = day_data.get("high")
            low_price = day_data.get("low")
            close_price = day_data.get("close")
            volume = day_data.get("volume")
            volume_avg = day_data.get("volume_avg")

            # Calculate derived fields
            intraday_character = None
            spx_range_pct = None
            vol_vs_avg = None

            if all(v is not None for v in [open_price, high_price, low_price, close_price]):
                intraday_character = classify_intraday_character(
                    open_price, high_price, low_price, close_price
                )
                if open_price > 0:
                    spx_range_pct = round((high_price - low_price) / open_price * 100, 2)

            if volume is not None and volume_avg is not None and volume_avg > 0:
                vol_vs_avg = round(volume / volume_avg, 2)

            # Only update if we have at least some data
            if intraday_character is not None or spx_range_pct is not None or vol_vs_avg is not None:
                conn.execute("""
                    UPDATE session_snapshots
                    SET intraday_character = COALESCE(?, intraday_character),
                        spx_intraday_range_pct = COALESCE(?, spx_intraday_range_pct),
                        volume_vs_20d_avg = COALESCE(?, volume_vs_20d_avg)
                    WHERE session_date = ?
                """, (
                    intraday_character,
                    spx_range_pct,
                    vol_vs_avg,
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
        # Count rows with/without intraday data
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN intraday_character IS NOT NULL THEN 1 ELSE 0 END) as has_character,
                SUM(CASE WHEN spx_intraday_range_pct IS NOT NULL THEN 1 ELSE 0 END) as has_range,
                SUM(CASE WHEN volume_vs_20d_avg IS NOT NULL THEN 1 ELSE 0 END) as has_volume
            FROM session_snapshots
        """)
        row = cursor.fetchone()

        print("\nBackfill Verification:")
        print(f"  Total snapshots: {row[0]}")
        print(f"  With intraday_character: {row[1]} ({row[1]/row[0]*100:.1f}%)")
        print(f"  With spx_intraday_range_pct: {row[2]} ({row[2]/row[0]*100:.1f}%)")
        print(f"  With volume_vs_20d_avg: {row[3]} ({row[3]/row[0]*100:.1f}%)")

        # Show sample of recent data
        print("\nRecent snapshots with intraday data:")
        cursor = conn.execute("""
            SELECT session_date, spx_change_pct, intraday_character,
                   spx_intraday_range_pct, volume_vs_20d_avg
            FROM session_snapshots
            WHERE intraday_character IS NOT NULL
            ORDER BY session_date DESC
            LIMIT 5
        """)
        for row in cursor.fetchall():
            char = row[2] or "N/A"
            range_pct = f"{row[3]:.2f}%" if row[3] else "N/A"
            vol = f"{row[4]:.2f}x" if row[4] else "N/A"
            print(f"  {row[0]}: SPX {row[1]:+.2f}% | {char:15} | Range: {range_pct:6} | Vol: {vol}")

        # Show character distribution
        print("\nIntraday character distribution:")
        cursor = conn.execute("""
            SELECT intraday_character, COUNT(*) as count
            FROM session_snapshots
            WHERE intraday_character IS NOT NULL
            GROUP BY intraday_character
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill intraday fields for session snapshots")
    parser.add_argument("--start", type=str, help="Start date YYYYMMDD")
    parser.add_argument("--end", type=str, help="End date YYYYMMDD")
    parser.add_argument("--verify", action="store_true", help="Only verify, don't backfill")
    parser.add_argument("--db", type=str, help="Custom database path")

    args = parser.parse_args()
    db_path = Path(args.db) if args.db else None

    if args.verify:
        verify_backfill(db_path)
    else:
        rows = backfill_intraday_fields(args.start, args.end, db_path)
        print(f"\nBackfill complete: {rows} rows updated")
        verify_backfill(db_path)

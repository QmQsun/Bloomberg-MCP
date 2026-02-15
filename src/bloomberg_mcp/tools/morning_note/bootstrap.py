"""Bootstrap script for populating historical data.

This module provides functions to:
1. Initialize the database schema
2. Backfill historical data from Bloomberg
3. Compute derived metrics and aggregates

Run once to populate history, then daily updates append new data.
"""

import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from .historical import get_db_connection, DEFAULT_DB_PATH
from .config import (
    US_INDEXES,
    SECTOR_ETFS,
    INDUSTRY_ETFS,
    JAPAN_PROXIES,
    MACRO_FX,
    MACRO_RATES,
    MACRO_COMMODITIES,
)
from .adr_screen import get_liquid_adrs_from_screen, classify_adr_sector


# =============================================================================
# SCHEMA INITIALIZATION
# =============================================================================

SCHEMA_SQL = """
-- Daily session snapshots (raw tool outputs)
CREATE TABLE IF NOT EXISTS session_snapshots (
    id INTEGER PRIMARY KEY,
    session_date DATE UNIQUE NOT NULL,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Store full tool outputs as JSON
    us_session_data JSON,
    japan_context JSON,

    -- Extracted key metrics for fast querying
    spx_change_pct REAL,
    spw_change_pct REAL,
    breadth_spread REAL,
    nasdaq_change_pct REAL,
    russell_change_pct REAL,

    dxy_change_pct REAL,
    usdjpy_change_pct REAL,
    us_10y_level REAL,
    us_10y_change_bps REAL,

    nikkei_futures_change_pct REAL,
    ewj_change_pct REAL,
    ewj_open_to_close_pct REAL,
    futures_ewj_divergence REAL,

    session_character TEXT,

    -- Beta: Extended market context (added 2024-12-23)
    vix_close REAL,
    vix_change_pct REAL,
    gold_close REAL,
    gold_change_pct REAL,
    us_2y_yield REAL,
    intraday_character TEXT,
    spx_intraday_range_pct REAL,
    volume_vs_20d_avg REAL
);

CREATE INDEX IF NOT EXISTS idx_session_date ON session_snapshots(session_date);

-- Sector performance history
CREATE TABLE IF NOT EXISTS sector_daily (
    id INTEGER PRIMARY KEY,
    session_date DATE NOT NULL,
    sector TEXT NOT NULL,
    name TEXT,
    change_pct REAL,
    volume REAL,
    volume_avg_20d REAL,
    rvol REAL,
    rank INTEGER,

    UNIQUE(session_date, sector)
);

CREATE INDEX IF NOT EXISTS idx_sector_date ON sector_daily(sector, session_date);

-- Industry ETF history
CREATE TABLE IF NOT EXISTS industry_daily (
    id INTEGER PRIMARY KEY,
    session_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    theme TEXT NOT NULL,
    change_pct REAL,
    rvol REAL,

    UNIQUE(session_date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_industry_theme_date ON industry_daily(theme, session_date);

-- ADR daily performance
CREATE TABLE IF NOT EXISTS adr_daily (
    id INTEGER PRIMARY KEY,
    session_date DATE NOT NULL,
    adr_ticker TEXT NOT NULL,
    jp_code TEXT NOT NULL,
    name TEXT,
    sector TEXT NOT NULL,
    change_pct REAL,
    rvol REAL,
    open_to_close_pct REAL,

    UNIQUE(session_date, adr_ticker)
);

CREATE INDEX IF NOT EXISTS idx_adr_sector_date ON adr_daily(sector, session_date);

-- Weekly aggregates
CREATE TABLE IF NOT EXISTS weekly_aggregates (
    id INTEGER PRIMARY KEY,
    week_ending DATE NOT NULL,
    ticker TEXT NOT NULL,
    ticker_type TEXT,
    total_volume REAL,
    avg_daily_volume REAL,
    weekly_change_pct REAL,
    weekly_high REAL,
    weekly_low REAL,

    UNIQUE(week_ending, ticker)
);

CREATE INDEX IF NOT EXISTS idx_weekly_ticker ON weekly_aggregates(ticker, week_ending);

-- Generated notes archive
CREATE TABLE IF NOT EXISTS notes_archive (
    id INTEGER PRIMARY KEY,
    session_date DATE UNIQUE NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    full_note TEXT,
    primary_theme TEXT,
    secondary_themes JSON,

    us_session_section TEXT,
    macro_section TEXT,
    japan_section TEXT,
    opening_bell_section TEXT,

    -- Beta: Enhanced metadata (added 2024-12-23)
    hypotheses_tested INTEGER DEFAULT 0,
    hypotheses_confirmed INTEGER DEFAULT 0,
    key_tickers TEXT,
    execution_time_seconds REAL,
    model_used TEXT,
    risk_tone TEXT,
    session_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_notes_date ON notes_archive(session_date);

-- Event markers
CREATE TABLE IF NOT EXISTS event_markers (
    id INTEGER PRIMARY KEY,
    session_date DATE NOT NULL,
    event_type TEXT NOT NULL,
    event_description TEXT,
    metadata JSON
);

CREATE INDEX IF NOT EXISTS idx_event_type_date ON event_markers(event_type, session_date DESC);

-- Thematic regimes
CREATE TABLE IF NOT EXISTS thematic_regimes (
    id INTEGER PRIMARY KEY,
    theme TEXT NOT NULL,
    regime TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    trigger_event TEXT,
    metadata JSON
);

CREATE INDEX IF NOT EXISTS idx_theme_regime ON thematic_regimes(theme, start_date DESC);

-- News events table - stores classified news for morning note context
-- Shared with news-mcp for historical news queries
CREATE TABLE IF NOT EXISTS news_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date DATE NOT NULL,           -- Session this news was collected for
    news_type TEXT NOT NULL,              -- macro, central_bank, sector, thematic, after_hours
    headline TEXT NOT NULL,
    summary TEXT,
    source TEXT,                          -- bloomberg.com, reuters.com, etc.
    source_url TEXT,
    tickers_json TEXT,                    -- JSON array of tickers mentioned
    sectors_json TEXT,                    -- JSON array of sectors affected
    themes_json TEXT,                     -- JSON array of themes
    sentiment TEXT,                       -- positive, negative, neutral, mixed
    japan_relevance REAL,                 -- 0-1 score for Japan equity relevance
    japan_readthroughs_json TEXT,         -- JSON of Japan ticker mappings
    published_date TIMESTAMP,             -- Actual article publication date (when available)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, headline)        -- Prevent duplicates
);

CREATE INDEX IF NOT EXISTS idx_news_events_date ON news_events(session_date);
CREATE INDEX IF NOT EXISTS idx_news_events_type ON news_events(news_type);
CREATE INDEX IF NOT EXISTS idx_news_events_sentiment ON news_events(sentiment);
"""


def init_database(db_path: Optional[Path] = None) -> None:
    """Initialize the database with schema.

    Safe to run multiple times - uses IF NOT EXISTS.
    """
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        print(f"Database initialized at: {path}")
    finally:
        conn.close()


# =============================================================================
# DATA ORGANIZATION HELPERS (DRY)
# =============================================================================

def _organize_by_date(hist_data: List[Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Organize historical data by date for easier processing.

    Pivots security-centric data into date-centric structure.

    Args:
        hist_data: List of HistoricalData objects from Bloomberg

    Returns:
        Dict[date_str, Dict[ticker, Dict[field, value]]]

    Example:
        >>> data_by_date = _organize_by_date(hist_data)
        >>> spx_on_date = data_by_date["2024-12-16"]["SPX Index"]["CHG_PCT_1D"]
    """
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

            # Store all fields for this ticker on this date
            data_by_date[date_str][ticker] = {
                k: v for k, v in point.items() if k != "date"
            }

    return data_by_date


def _get_ticker_maps() -> Dict[str, Dict[str, str]]:
    """Build ticker lookup maps from config for DRY access.

    Returns:
        Dict with keys: indexes, proxies, fx, rates, commodities
        Each value is Dict[config_key, ticker_string]
    """
    return {
        "indexes": {k: v.ticker for k, v in US_INDEXES.items()},
        "proxies": {k: v.ticker for k, v in JAPAN_PROXIES.items()},
        "fx": {k: v.ticker for k, v in MACRO_FX.items()},
        "rates": {k: v.ticker for k, v in MACRO_RATES.items()},
        "commodities": {k: v.ticker for k, v in MACRO_COMMODITIES.items()},
        "sectors": {etf.ticker: etf.name for etf in SECTOR_ETFS},
        "industries": {
            etf.ticker: {"name": etf.name, "theme": theme}
            for theme, etfs in INDUSTRY_ETFS.items()
            for etf in etfs
        },
    }


# =============================================================================
# SESSION SNAPSHOTS BACKFILL
# =============================================================================

def _build_session_snapshots(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> None:
    """Build session_snapshots from historical Bloomberg data.

    Fetches index, macro (FX, rates), and Japan proxy data to populate
    the session_snapshots table with key metrics for historical queries.

    Note: Full JSON snapshots (us_session_data, japan_context) and intraday
    metrics (ewj_open_to_close_pct) cannot be backfilled - only available
    for live captures.

    Args:
        conn: Database connection
        start_date: Start date YYYYMMDD
        end_date: End date YYYYMMDD
    """
    from ..historical import get_historical_data

    # Collect all tickers needed for session snapshots
    session_tickers = []

    # US Indexes (for breadth analysis)
    session_tickers.extend([idx.ticker for idx in US_INDEXES.values()])

    # Japan proxies (for futures/EWJ divergence)
    session_tickers.extend([p.ticker for p in JAPAN_PROXIES.values()])

    # Macro - FX
    session_tickers.extend([fx.ticker for fx in MACRO_FX.values()])

    # Macro - Rates
    session_tickers.extend([rate.ticker for rate in MACRO_RATES.values()])

    print(f"Fetching session snapshot data: {len(session_tickers)} securities...")

    fields = ["PX_LAST", "CHG_PCT_1D"]

    hist_data = get_historical_data(
        securities=session_tickers,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        periodicity="DAILY",
    )

    # Organize by date
    data_by_date = _organize_by_date(hist_data)

    print(f"Building session snapshots for {len(data_by_date)} dates...")

    # Get ticker maps
    maps = _get_ticker_maps()
    idx = maps["indexes"]
    proxy = maps["proxies"]
    fx = maps["fx"]
    rates = maps["rates"]

    rows_inserted = 0
    for session_date in sorted(data_by_date.keys()):
        day_data = data_by_date[session_date]

        # Helper closures for clean access
        def get_change(ticker: str) -> Optional[float]:
            return day_data.get(ticker, {}).get("CHG_PCT_1D")

        def get_last(ticker: str) -> Optional[float]:
            return day_data.get(ticker, {}).get("PX_LAST")

        # US Index changes
        spx_change = get_change(idx["spx"])
        spw_change = get_change(idx["spw"])
        nasdaq_change = get_change(idx["nasdaq"])
        russell_change = get_change(idx["russell"])

        # Breadth spread (SPX - SPW: positive = narrow leadership)
        breadth_spread = None
        if spx_change is not None and spw_change is not None:
            breadth_spread = round(spx_change - spw_change, 4)

        # Macro - FX
        dxy_change = get_change(fx["dxy"])
        usdjpy_change = get_change(fx["usdjpy"])

        # Macro - Rates
        us_10y_level = get_last(rates["us_10y"])
        us_10y_change = get_change(rates["us_10y"])

        # Japan proxies
        nk_futures_change = get_change(proxy["nikkei_futures"])
        ewj_change = get_change(proxy["ewj"])

        # Futures vs EWJ divergence
        futures_ewj_div = None
        if nk_futures_change is not None and ewj_change is not None:
            futures_ewj_div = round(nk_futures_change - ewj_change, 4)

        conn.execute("""
            INSERT OR IGNORE INTO session_snapshots (
                session_date,
                spx_change_pct, spw_change_pct, breadth_spread,
                nasdaq_change_pct, russell_change_pct,
                dxy_change_pct, usdjpy_change_pct,
                us_10y_level, us_10y_change_bps,
                nikkei_futures_change_pct, ewj_change_pct,
                futures_ewj_divergence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_date,
            spx_change, spw_change, breadth_spread,
            nasdaq_change, russell_change,
            dxy_change, usdjpy_change,
            us_10y_level, us_10y_change,
            nk_futures_change, ewj_change,
            futures_ewj_div,
        ))
        rows_inserted += 1

    print(f"Inserted {rows_inserted} session snapshots")


# =============================================================================
# INSTRUMENT-LEVEL BACKFILL (Sectors, Industries, ADRs)
# =============================================================================

def _build_instrument_data(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
    adr_map: Dict[str, Dict],
) -> None:
    """Build sector, industry, and ADR daily data from Bloomberg.

    Args:
        conn: Database connection
        start_date: Start date YYYYMMDD
        end_date: End date YYYYMMDD
        adr_map: ADR metadata from EQS screen (ticker -> {jp_code, name, sector})
    """
    from ..historical import get_historical_data

    maps = _get_ticker_maps()

    # Collect tickers by category
    categories = {
        "sectors": [etf.ticker for etf in SECTOR_ETFS],
        "industries": list(maps["industries"].keys()),
        "adrs": list(adr_map.keys()),
    }

    fields = ["PX_LAST", "CHG_PCT_1D", "VOLUME", "VOLUME_AVG_20D"]

    for category, tickers in categories.items():
        if not tickers:
            continue

        print(f"Fetching {category}: {len(tickers)} securities...")

        hist_data = get_historical_data(
            securities=tickers,
            fields=fields,
            start_date=start_date,
            end_date=end_date,
            periodicity="DAILY",
        )

        # Process by security
        for sec_data in hist_data:
            ticker = sec_data.security

            for point in sec_data.data:
                session_date = point.get("date")
                if isinstance(session_date, datetime):
                    session_date = session_date.strftime("%Y-%m-%d")

                change_pct = point.get("CHG_PCT_1D")
                volume = point.get("VOLUME")
                vol_avg = point.get("VOLUME_AVG_20D")
                rvol = volume / vol_avg if volume and vol_avg and vol_avg > 0 else None

                if category == "sectors":
                    name = maps["sectors"].get(ticker)
                    conn.execute("""
                        INSERT OR IGNORE INTO sector_daily
                        (session_date, sector, name, change_pct, volume, volume_avg_20d, rvol)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (session_date, ticker, name, change_pct, volume, vol_avg, rvol))

                elif category == "industries":
                    info = maps["industries"].get(ticker, {})
                    conn.execute("""
                        INSERT OR IGNORE INTO industry_daily
                        (session_date, ticker, name, theme, change_pct, rvol)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (session_date, ticker, info.get("name"), info.get("theme", ""), change_pct, rvol))

                elif category == "adrs":
                    info = adr_map.get(ticker, {})
                    conn.execute("""
                        INSERT OR IGNORE INTO adr_daily
                        (session_date, adr_ticker, jp_code, name, sector, change_pct, rvol)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (session_date, ticker, info.get("jp_code", ""), info.get("name"), info.get("sector", ""), change_pct, rvol))


# =============================================================================
# MAIN BOOTSTRAP FUNCTION
# =============================================================================

def bootstrap_from_bloomberg(
    start_date: str,
    end_date: str,
    db_path: Optional[Path] = None,
) -> None:
    """Backfill historical data from Bloomberg.

    Populates all historical tables:
    - session_snapshots: Daily session-level metrics
    - sector_daily: Sector ETF performance
    - industry_daily: Industry/thematic ETF performance
    - adr_daily: Japan ADR performance (from EQS screen universe)
    - weekly_aggregates: Weekly rollups

    ADRs are fetched dynamically from the Japan_Liquid_ADRs EQS screen.

    Args:
        start_date: Start date YYYYMMDD
        end_date: End date YYYYMMDD
        db_path: Optional database path

    Example:
        >>> bootstrap_from_bloomberg("20241217", "20251217")
    """
    print(f"Bootstrapping history from {start_date} to {end_date}")

    # Initialize database
    init_database(db_path)

    # Fetch ADR universe from EQS screen
    adr_data = get_liquid_adrs_from_screen()
    print(f"ADR universe from EQS screen: {len(adr_data)} ADRs")

    # Build ADR metadata map
    adr_map: Dict[str, Dict] = {}
    for adr in adr_data:
        ticker = adr.get("security") or adr.get("Ticker")
        if ticker and not ticker.endswith(" Equity"):
            ticker = f"{ticker} Equity"

        # Classify sector using GICS data from screen
        sector = classify_adr_sector(
            gics_sector=adr.get("GICS Sector"),
            gics_subind=adr.get("GICS SubInd Name"),
        )

        adr_map[ticker] = {
            "jp_code": adr.get("Und Tkr", ""),
            "name": adr.get("Short Name", ""),
            "sector": sector,
        }

    conn = get_db_connection(db_path)

    try:
        # 1. Build session snapshots (indexes, macro, proxies)
        _build_session_snapshots(conn, start_date, end_date)

        # 2. Build instrument-level data (sectors, industries, ADRs)
        _build_instrument_data(conn, start_date, end_date, adr_map)

        # 3. Compute sector ranks
        print("Computing sector ranks...")
        _compute_sector_ranks_internal(conn)

        # 4. Compute weekly aggregates
        print("Computing weekly aggregates...")
        _compute_all_weekly_aggregates(conn, start_date, end_date)

        conn.commit()
        print("Bootstrap complete!")

        # Print summary
        _print_bootstrap_summary(conn)

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def _print_bootstrap_summary(conn: sqlite3.Connection) -> None:
    """Print summary of bootstrapped data."""
    tables = [
        "session_snapshots",
        "sector_daily",
        "industry_daily",
        "adr_daily",
        "weekly_aggregates",
    ]
    print("\nBootstrap Summary:")
    print("-" * 40)
    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count:,} rows")


# =============================================================================
# DERIVED COMPUTATIONS
# =============================================================================

def _compute_sector_ranks_internal(conn: sqlite3.Connection) -> None:
    """Compute sector ranks for all dates in the database."""
    # Get all unique dates
    cursor = conn.execute("SELECT DISTINCT session_date FROM sector_daily ORDER BY session_date")
    dates = [row[0] for row in cursor.fetchall()]

    for session_date in dates:
        # Get sectors for this date ordered by change
        cursor = conn.execute("""
            SELECT id, change_pct FROM sector_daily
            WHERE session_date = ?
            ORDER BY change_pct DESC
        """, (session_date,))

        rows = cursor.fetchall()
        for rank, (row_id, _) in enumerate(rows, 1):
            conn.execute("UPDATE sector_daily SET rank = ? WHERE id = ?", (rank, row_id))


def compute_sector_ranks(db_path: Optional[Path] = None) -> None:
    """Compute sector ranks for all historical data.

    Run this after bootstrap to populate rank field.
    """
    conn = get_db_connection(db_path)

    try:
        _compute_sector_ranks_internal(conn)
        conn.commit()

        cursor = conn.execute("SELECT COUNT(DISTINCT session_date) FROM sector_daily")
        count = cursor.fetchone()[0]
        print(f"Computed ranks for {count} dates")
    finally:
        conn.close()


def _compute_all_weekly_aggregates(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> None:
    """Compute weekly aggregates for all data."""
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    weeks_processed = 0

    # Find all Fridays in range
    current = start
    while current <= end:
        if current.weekday() == 4:  # Friday
            friday_str = current.strftime("%Y-%m-%d")
            monday_str = (current - timedelta(days=4)).strftime("%Y-%m-%d")

            # Sectors
            conn.execute("""
                INSERT OR IGNORE INTO weekly_aggregates (
                    week_ending, ticker, ticker_type,
                    total_volume, avg_daily_volume, weekly_change_pct
                )
                SELECT
                    ?, sector, 'sector',
                    SUM(volume), AVG(volume), SUM(change_pct)
                FROM sector_daily
                WHERE session_date BETWEEN ? AND ?
                GROUP BY sector
            """, (friday_str, monday_str, friday_str))

            # Industry ETFs
            conn.execute("""
                INSERT OR IGNORE INTO weekly_aggregates (
                    week_ending, ticker, ticker_type, weekly_change_pct
                )
                SELECT ?, ticker, 'industry', SUM(change_pct)
                FROM industry_daily
                WHERE session_date BETWEEN ? AND ?
                GROUP BY ticker
            """, (friday_str, monday_str, friday_str))

            # ADRs
            conn.execute("""
                INSERT OR IGNORE INTO weekly_aggregates (
                    week_ending, ticker, ticker_type, weekly_change_pct
                )
                SELECT ?, adr_ticker, 'adr', SUM(change_pct)
                FROM adr_daily
                WHERE session_date BETWEEN ? AND ?
                GROUP BY adr_ticker
            """, (friday_str, monday_str, friday_str))

            weeks_processed += 1

        current += timedelta(days=1)

    print(f"Processed {weeks_processed} weeks")


# =============================================================================
# SAMPLE DATA FOR TESTING
# =============================================================================

def insert_sample_data(db_path: Optional[Path] = None) -> None:
    """Insert sample data for testing without Bloomberg connection.

    Creates 10 days of synthetic data.
    """
    init_database(db_path)
    conn = get_db_connection(db_path)

    import random
    random.seed(42)

    base_date = date.today() - timedelta(days=10)

    try:
        for day_offset in range(10):
            session_date = (base_date + timedelta(days=day_offset)).isoformat()

            if (base_date + timedelta(days=day_offset)).weekday() >= 5:
                continue  # Skip weekends

            # Session snapshot
            spx_change = random.uniform(-1.5, 1.5)
            spw_change = spx_change + random.uniform(-0.5, 0.5)
            breadth = spx_change - spw_change

            conn.execute("""
                INSERT OR REPLACE INTO session_snapshots (
                    session_date, spx_change_pct, spw_change_pct, breadth_spread,
                    nasdaq_change_pct, russell_change_pct,
                    dxy_change_pct, usdjpy_change_pct,
                    nikkei_futures_change_pct, ewj_change_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_date, spx_change, spw_change, breadth,
                spx_change + random.uniform(-0.5, 0.5),
                spx_change + random.uniform(-0.3, 0.3),
                random.uniform(-0.5, 0.5),
                random.uniform(-0.3, 0.3),
                random.uniform(-1.0, 1.0),
                random.uniform(-1.5, 1.5),
            ))

            # Sector data
            sectors = ["XLK", "XLF", "XLE", "XLV", "XLP", "XLI", "XLB", "XLRE", "XLU", "XLC", "XLY"]
            sector_names = ["Technology", "Financials", "Energy", "Healthcare", "Consumer Staples",
                           "Industrials", "Materials", "Real Estate", "Utilities", "Communication Services",
                           "Consumer Discretionary"]
            changes = [random.uniform(-2, 2) for _ in sectors]
            sorted_indices = sorted(range(len(changes)), key=lambda i: changes[i], reverse=True)

            for rank, idx in enumerate(sorted_indices, 1):
                conn.execute("""
                    INSERT OR REPLACE INTO sector_daily (
                        session_date, sector, name, change_pct, rvol, rank
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    session_date, sectors[idx], sector_names[idx],
                    changes[idx], random.uniform(0.7, 2.0), rank
                ))

            # ADR data
            adrs = [
                ("MUFG US Equity", "8306 JP Equity", "Mitsubishi UFJ", "banks"),
                ("TM US Equity", "7203 JP Equity", "Toyota", "autos"),
                ("SONY US Equity", "6758 JP Equity", "Sony", "tech"),
                ("TOELY US Equity", "8035 JP Equity", "Tokyo Electron", "semiconductors"),
            ]
            for adr_ticker, jp_code, name, sector in adrs:
                conn.execute("""
                    INSERT OR REPLACE INTO adr_daily (
                        session_date, adr_ticker, jp_code, name, sector, change_pct, rvol
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_date, adr_ticker, jp_code, name, sector,
                      random.uniform(-3, 3), random.uniform(0.5, 3.0)))

        # Add some events
        conn.execute("""
            INSERT INTO event_markers (session_date, event_type, event_description, metadata)
            VALUES (?, ?, ?, ?)
        """, (base_date.isoformat(), "extreme_breadth", "SPX vs SPW spread of 0.92%",
              '{"breadth_spread": 0.92, "direction": "narrow"}'))

        conn.commit()
        print("Sample data inserted successfully")

    finally:
        conn.close()


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap morning note historical data")
    parser.add_argument("--init", action="store_true", help="Initialize database schema")
    parser.add_argument("--sample", action="store_true", help="Insert sample data for testing")
    parser.add_argument("--bootstrap", nargs=2, metavar=("START", "END"),
                       help="Bootstrap from Bloomberg (YYYYMMDD YYYYMMDD)")
    parser.add_argument("--ranks", action="store_true", help="Compute sector ranks")
    parser.add_argument("--db", type=str, help="Custom database path")

    args = parser.parse_args()
    db_path = Path(args.db) if args.db else None

    if args.init:
        init_database(db_path)
    elif args.sample:
        insert_sample_data(db_path)
    elif args.bootstrap:
        bootstrap_from_bloomberg(args.bootstrap[0], args.bootstrap[1], db_path)
    elif args.ranks:
        compute_sector_ranks(db_path)
    else:
        parser.print_help()

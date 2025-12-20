"""Storage and event detection for morning note historical data.

This module handles:
- Storing daily session data to SQLite
- Detecting and recording notable events
- Managing weekly aggregates
- Archiving generated notes

The storage layer bridges the live Bloomberg tools with the historical context layer.
"""

import json
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import USSessionSnapshot, JapanOvernightSnapshot
from .historical import get_db_connection, DEFAULT_DB_PATH


# =============================================================================
# SESSION STORAGE
# =============================================================================

def store_session_snapshot(
    us_snapshot: USSessionSnapshot,
    japan_snapshot: Optional[JapanOvernightSnapshot] = None,
    session_character: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Store a complete session snapshot to the database.

    This is the primary ingestion function - call after each session.

    Args:
        us_snapshot: USSessionSnapshot from get_us_session_snapshot()
        japan_snapshot: Optional JapanOvernightSnapshot
        session_character: Optional LLM-assigned session character

    Example:
        >>> us = get_us_session_snapshot()
        >>> jp = get_japan_overnight_snapshot()
        >>> store_session_snapshot(us, jp, session_character="rotation to value")
    """
    conn = get_db_connection(db_path)
    session_date = us_snapshot.session_date

    try:
        # Extract key metrics from US snapshot
        spx = us_snapshot.indexes.get("spx")
        spw = us_snapshot.indexes.get("spw")
        nasdaq = us_snapshot.indexes.get("nasdaq")
        russell = us_snapshot.indexes.get("russell")

        spx_change = spx.price.change_pct if spx else None
        spw_change = spw.price.change_pct if spw else None
        nasdaq_change = nasdaq.price.change_pct if nasdaq else None
        russell_change = russell.price.change_pct if russell else None

        breadth_spread = us_snapshot.breadth.spread

        # Macro
        dxy_change = us_snapshot.macro.dxy.change_pct
        usdjpy_change = us_snapshot.macro.usdjpy.change_pct
        us_10y = us_snapshot.macro.yields.us_10y
        us_10y_change = us_snapshot.macro.us_10y_change_pct

        # Japan metrics
        nk_futures_change = None
        ewj_change = None
        ewj_otc = None
        futures_ewj_div = None

        if japan_snapshot:
            nk_futures_change = japan_snapshot.proxies.nikkei_futures.price.change_pct
            ewj_change = japan_snapshot.proxies.ewj.price.change_pct
            ewj_otc = japan_snapshot.proxies.ewj_open_to_close_pct
            futures_ewj_div = japan_snapshot.proxies.futures_vs_ewj_divergence

        # Store main snapshot
        conn.execute("""
            INSERT OR REPLACE INTO session_snapshots (
                session_date, captured_at,
                us_session_data, japan_context,
                spx_change_pct, spw_change_pct, breadth_spread,
                nasdaq_change_pct, russell_change_pct,
                dxy_change_pct, usdjpy_change_pct,
                us_10y_level, us_10y_change_bps,
                nikkei_futures_change_pct, ewj_change_pct,
                ewj_open_to_close_pct, futures_ewj_divergence,
                session_character
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_date,
            datetime.now().isoformat(),
            us_snapshot.model_dump_json(),
            japan_snapshot.model_dump_json() if japan_snapshot else None,
            spx_change,
            spw_change,
            breadth_spread,
            nasdaq_change,
            russell_change,
            dxy_change,
            usdjpy_change,
            us_10y,
            us_10y_change,
            nk_futures_change,
            ewj_change,
            ewj_otc,
            futures_ewj_div,
            session_character,
        ))

        # Store sector daily data
        _store_sector_data(conn, session_date, us_snapshot)

        # Store industry daily data
        _store_industry_data(conn, session_date, us_snapshot)

        # Store ADR daily data
        if japan_snapshot:
            _store_adr_data(conn, session_date, japan_snapshot)

        # Detect and store events
        _detect_and_store_events(conn, session_date, us_snapshot, japan_snapshot)

        # Update weekly aggregates if Friday
        if datetime.strptime(session_date, "%Y-%m-%d").weekday() == 4:
            _update_weekly_aggregates(conn, session_date)

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def _store_sector_data(
    conn: sqlite3.Connection,
    session_date: str,
    snapshot: USSessionSnapshot,
) -> None:
    """Store sector daily performance."""
    for sector in snapshot.sectors:
        rvol = None
        if sector.volume:
            rvol = sector.volume.relative_volume

        conn.execute("""
            INSERT OR REPLACE INTO sector_daily (
                session_date, sector, name, change_pct, volume, volume_avg_20d, rvol, rank
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_date,
            sector.ticker,
            sector.name,
            sector.change_pct,
            sector.volume.volume if sector.volume else None,
            sector.volume.avg_20d if sector.volume else None,
            rvol,
            sector.rank,
        ))


def _store_industry_data(
    conn: sqlite3.Connection,
    session_date: str,
    snapshot: USSessionSnapshot,
) -> None:
    """Store industry ETF daily performance."""
    for theme, etfs in snapshot.industry_etfs.items():
        for etf in etfs:
            rvol = None
            if etf.volume:
                rvol = etf.volume.relative_volume

            conn.execute("""
                INSERT OR REPLACE INTO industry_daily (
                    session_date, ticker, name, theme, change_pct, rvol
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_date,
                etf.ticker,
                etf.name,
                theme,
                etf.change_pct,
                rvol,
            ))


def _store_adr_data(
    conn: sqlite3.Connection,
    session_date: str,
    snapshot: JapanOvernightSnapshot,
) -> None:
    """Store ADR daily performance."""
    for sector_summary in snapshot.adr_sectors.values():
        for adr in sector_summary.adrs:
            rvol = None
            if adr.volume:
                rvol = adr.volume.relative_volume

            conn.execute("""
                INSERT OR REPLACE INTO adr_daily (
                    session_date, adr_ticker, jp_code, name, sector,
                    change_pct, rvol, open_to_close_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_date,
                adr.adr_ticker,
                adr.jp_code,
                adr.name,
                adr.sector,
                adr.change_pct,
                rvol,
                adr.open_to_close_pct,
            ))


# =============================================================================
# EVENT DETECTION
# =============================================================================

def _detect_and_store_events(
    conn: sqlite3.Connection,
    session_date: str,
    us_snapshot: USSessionSnapshot,
    japan_snapshot: Optional[JapanOvernightSnapshot],
) -> None:
    """Detect notable events and store them."""
    events = []

    # 1. Breadth extremes
    breadth = us_snapshot.breadth.spread
    if abs(breadth) > 0.8:
        events.append({
            "event_type": "extreme_breadth",
            "description": f"SPX vs SPW spread of {breadth:.2f}%",
            "metadata": {
                "breadth_spread": breadth,
                "direction": "narrow" if breadth > 0 else "broad",
            }
        })

    # 2. Large SPX moves
    spx = us_snapshot.indexes.get("spx")
    if spx and abs(spx.price.change_pct) > 1.5:
        events.append({
            "event_type": "large_spx_move",
            "description": f"SPX moved {spx.price.change_pct:.2f}%",
            "metadata": {
                "change_pct": spx.price.change_pct,
                "direction": "up" if spx.price.change_pct > 0 else "down",
            }
        })

    # 3. Sector extremes (top/bottom with high RVOL)
    for sector in us_snapshot.sectors:
        if sector.volume and sector.volume.relative_volume > 2.0:
            if sector.rank <= 2 or sector.rank >= 10:
                events.append({
                    "event_type": "sector_volume_extreme",
                    "description": f"{sector.name} rank {sector.rank} with RVOL {sector.volume.relative_volume:.1f}x",
                    "metadata": {
                        "sector": sector.ticker,
                        "rank": sector.rank,
                        "rvol": sector.volume.relative_volume,
                        "change_pct": sector.change_pct,
                    }
                })

    # 4. Japan proxy divergence
    if japan_snapshot:
        divergence = japan_snapshot.proxies.futures_vs_ewj_divergence
        if abs(divergence) > 1.5:
            events.append({
                "event_type": "futures_ewj_divergence",
                "description": f"Nikkei futures vs EWJ diverged {divergence:.2f}%",
                "metadata": {
                    "divergence": divergence,
                    "direction": "futures_stronger" if divergence > 0 else "ewj_stronger",
                }
            })

        # 5. ADR volume extremes
        for sector_summary in japan_snapshot.adr_sectors.values():
            for adr in sector_summary.adrs:
                if adr.volume and adr.volume.relative_volume > 2.5:
                    events.append({
                        "event_type": "adr_volume_extreme",
                        "description": f"{adr.adr_ticker} RVOL {adr.volume.relative_volume:.1f}x, {adr.change_pct:+.2f}%",
                        "metadata": {
                            "ticker": adr.adr_ticker,
                            "jp_code": adr.jp_code,
                            "sector": adr.sector,
                            "rvol": adr.volume.relative_volume,
                            "change_pct": adr.change_pct,
                        }
                    })

    # 6. Macro extremes
    if abs(us_snapshot.macro.dxy.change_pct) > 0.8:
        events.append({
            "event_type": "dxy_extreme",
            "description": f"DXY moved {us_snapshot.macro.dxy.change_pct:.2f}%",
            "metadata": {
                "change_pct": us_snapshot.macro.dxy.change_pct,
            }
        })

    if abs(us_snapshot.macro.usdjpy.change_pct) > 0.8:
        events.append({
            "event_type": "usdjpy_extreme",
            "description": f"USDJPY moved {us_snapshot.macro.usdjpy.change_pct:.2f}%",
            "metadata": {
                "change_pct": us_snapshot.macro.usdjpy.change_pct,
            }
        })

    # Store all events
    for event in events:
        conn.execute("""
            INSERT INTO event_markers (session_date, event_type, event_description, metadata)
            VALUES (?, ?, ?, ?)
        """, (
            session_date,
            event["event_type"],
            event["description"],
            json.dumps(event["metadata"]),
        ))


def detect_sector_streaks(
    conn: sqlite3.Connection,
    session_date: str,
    min_streak: int = 3,
) -> List[Dict[str, Any]]:
    """Detect and return sector leadership streaks (for event storage)."""
    # This is called separately to detect streak starts/extensions
    query = """
        SELECT sector, session_date, rank
        FROM sector_daily
        WHERE session_date <= ?
        ORDER BY sector, session_date DESC
    """

    cursor = conn.execute(query, [session_date])

    # Group by sector
    sector_days: Dict[str, List[int]] = {}
    for row in cursor.fetchall():
        sector = row["sector"]
        if sector not in sector_days:
            sector_days[sector] = []
        sector_days[sector].append(row["rank"])

    streaks = []
    for sector, ranks in sector_days.items():
        # Check leader streak
        leader_streak = 0
        for rank in ranks:
            if rank and rank <= 3:
                leader_streak += 1
            else:
                break

        if leader_streak == min_streak:  # Just hit threshold
            streaks.append({
                "sector": sector,
                "streak_type": "leader",
                "streak_days": leader_streak,
            })

        # Check laggard streak
        laggard_streak = 0
        for rank in ranks:
            if rank and rank >= 9:
                laggard_streak += 1
            else:
                break

        if laggard_streak == min_streak:  # Just hit threshold
            streaks.append({
                "sector": sector,
                "streak_type": "laggard",
                "streak_days": laggard_streak,
            })

    return streaks


# =============================================================================
# WEEKLY AGGREGATES
# =============================================================================

def _update_weekly_aggregates(
    conn: sqlite3.Connection,
    friday_date: str,
) -> None:
    """Update weekly aggregates (called on Fridays)."""
    friday = datetime.strptime(friday_date, "%Y-%m-%d")
    monday = (friday - timedelta(days=4)).strftime("%Y-%m-%d")

    # Aggregate sectors
    conn.execute("""
        INSERT OR REPLACE INTO weekly_aggregates (
            week_ending, ticker, ticker_type,
            total_volume, avg_daily_volume, weekly_change_pct
        )
        SELECT
            ?,
            sector,
            'sector',
            SUM(volume),
            AVG(volume),
            SUM(change_pct)
        FROM sector_daily
        WHERE session_date BETWEEN ? AND ?
        GROUP BY sector
    """, (friday_date, monday, friday_date))

    # Aggregate industry ETFs
    conn.execute("""
        INSERT OR REPLACE INTO weekly_aggregates (
            week_ending, ticker, ticker_type,
            weekly_change_pct
        )
        SELECT
            ?,
            ticker,
            'industry',
            SUM(change_pct)
        FROM industry_daily
        WHERE session_date BETWEEN ? AND ?
        GROUP BY ticker
    """, (friday_date, monday, friday_date))

    # Aggregate ADRs
    conn.execute("""
        INSERT OR REPLACE INTO weekly_aggregates (
            week_ending, ticker, ticker_type,
            weekly_change_pct
        )
        SELECT
            ?,
            adr_ticker,
            'adr',
            SUM(change_pct)
        FROM adr_daily
        WHERE session_date BETWEEN ? AND ?
        GROUP BY adr_ticker
    """, (friday_date, monday, friday_date))


# =============================================================================
# NOTE ARCHIVING
# =============================================================================

def archive_note(
    session_date: str,
    full_note: str,
    primary_theme: Optional[str] = None,
    secondary_themes: Optional[List[str]] = None,
    us_section: Optional[str] = None,
    macro_section: Optional[str] = None,
    japan_section: Optional[str] = None,
    opening_bell_section: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Archive a generated morning note.

    Args:
        session_date: Session date YYYY-MM-DD
        full_note: Complete note text
        primary_theme: Main theme of the note
        secondary_themes: List of secondary themes
        us_section: US markets section
        macro_section: Macro section
        japan_section: Japan section
        opening_bell_section: Opening bell section
    """
    conn = get_db_connection(db_path)

    try:
        conn.execute("""
            INSERT OR REPLACE INTO notes_archive (
                session_date, generated_at,
                full_note, primary_theme, secondary_themes,
                us_session_section, macro_section, japan_section, opening_bell_section
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_date,
            datetime.now().isoformat(),
            full_note,
            primary_theme,
            json.dumps(secondary_themes) if secondary_themes else None,
            us_section,
            macro_section,
            japan_section,
            opening_bell_section,
        ))
        conn.commit()
    finally:
        conn.close()


def update_session_character(
    session_date: str,
    session_character: str,
    db_path: Optional[Path] = None,
) -> None:
    """Update the session character for a stored session.

    Call this after LLM analysis assigns a character.
    """
    conn = get_db_connection(db_path)

    try:
        conn.execute("""
            UPDATE session_snapshots
            SET session_character = ?
            WHERE session_date = ?
        """, (session_character, session_date))
        conn.commit()
    finally:
        conn.close()


def add_thematic_regime(
    theme: str,
    regime: str,
    start_date: str,
    trigger_event: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Add a new thematic regime.

    Args:
        theme: Theme name (e.g., "robotics", "AI_infrastructure")
        regime: Regime type ("bottoming", "accumulation", "distribution", "trending")
        start_date: When regime started
        trigger_event: What triggered the regime change
        metadata: Additional metadata
    """
    conn = get_db_connection(db_path)

    try:
        conn.execute("""
            INSERT INTO thematic_regimes (theme, regime, start_date, trigger_event, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            theme,
            regime,
            start_date,
            trigger_event,
            json.dumps(metadata) if metadata else None,
        ))
        conn.commit()
    finally:
        conn.close()


def end_thematic_regime(
    theme: str,
    end_date: str,
    db_path: Optional[Path] = None,
) -> None:
    """End an active thematic regime."""
    conn = get_db_connection(db_path)

    try:
        conn.execute("""
            UPDATE thematic_regimes
            SET end_date = ?
            WHERE theme = ? AND end_date IS NULL
        """, (end_date, theme))
        conn.commit()
    finally:
        conn.close()

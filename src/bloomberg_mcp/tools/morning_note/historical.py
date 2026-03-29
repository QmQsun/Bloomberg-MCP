"""Historical context layer for morning note generation.

This module provides two tiers of historical data access:

1. STRUCTURED TOOLS (consistent usage patterns):
   - get_historical_context() - Standard context for morning note generation
   - get_sector_streaks() - Current sector leadership/laggard streaks
   - get_yesterday_themes() - Prior note themes for continuity

2. EXPLORATORY TOOLS (flexible querying):
   - query_sessions() - Flexible session history queries with filters
   - find_similar_sessions() - Pattern matching for "last time X happened"
   - query_sector_history() - Deep dive into sector trends
   - query_adr_history() - ADR pattern analysis
   - get_volume_trends() - Weekly volume pattern analysis
   - get_event_history() - Historical event markers

Design Philosophy:
- Structured tools return Pydantic models for type safety
- Exploratory tools return dicts for flexibility
- All tools use the same underlying SQLite database
- Agents can start with structured tools, then explore deeper
"""

import json
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field, computed_field

# Database path - configurable
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "morning_note_history.db"


# =============================================================================
# PYDANTIC MODELS FOR STRUCTURED TOOLS
# =============================================================================

class SessionSummary(BaseModel):
    """Summary of a historical session."""
    session_date: str
    spx_change_pct: float
    breadth_spread: float
    nasdaq_vs_spx: Optional[float] = None
    russell_vs_spx: Optional[float] = None
    session_character: Optional[str] = None
    primary_theme: Optional[str] = None


class SectorStreak(BaseModel):
    """Sector leadership or laggard streak."""
    sector: str
    name: str
    streak_type: Literal["leader", "laggard"]
    streak_days: int
    cumulative_return_pct: float
    avg_rank: float = Field(description="Average rank during streak")

    @computed_field
    @property
    def is_notable(self) -> bool:
        """Streak of 3+ days is notable."""
        return self.streak_days >= 3


class ExtremeEvent(BaseModel):
    """Historical extreme for context."""
    event_type: str
    event_date: str
    days_ago: int
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ThematicRegime(BaseModel):
    """Active thematic regime."""
    theme: str
    regime: str = Field(description="bottoming, accumulation, distribution, trending")
    start_date: str
    days_active: int
    trigger_event: Optional[str] = None


class HistoricalContext(BaseModel):
    """Complete historical context for morning note generation.

    This is the primary structured output for the standard workflow.
    """
    as_of: datetime

    # Recent sessions for continuity
    recent_sessions: List[SessionSummary] = Field(
        description="Last 5 sessions with key metrics"
    )

    # Current streaks
    sector_streaks: List[SectorStreak] = Field(
        description="Sectors with 3+ day leadership or laggard streaks"
    )

    # Relevant extremes based on current conditions
    recent_events: List[ExtremeEvent] = Field(
        description="Notable events in last 20 sessions"
    )

    # Thematic context
    active_regimes: List[ThematicRegime] = Field(
        description="Currently active thematic regimes"
    )

    # Yesterday's note themes (for continuity)
    yesterday_primary_theme: Optional[str] = None
    yesterday_secondary_themes: List[str] = Field(default_factory=list)

    # Summary stats
    @computed_field
    @property
    def spx_5d_return(self) -> float:
        """SPX cumulative return over last 5 sessions."""
        if len(self.recent_sessions) >= 5:
            return round(sum(s.spx_change_pct for s in self.recent_sessions[:5]), 2)
        return 0.0

    @computed_field
    @property
    def avg_breadth_5d(self) -> float:
        """Average breadth spread over last 5 sessions."""
        if len(self.recent_sessions) >= 5:
            return round(sum(s.breadth_spread for s in self.recent_sessions[:5]) / 5, 2)
        return 0.0


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get SQLite database connection."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# STRUCTURED TOOLS (Consistent Usage Patterns)
# =============================================================================

def get_historical_context(
    session_date: Optional[str] = None,
    lookback_days: int = 20,
    db_path: Optional[Path] = None,
) -> HistoricalContext:
    """Get structured historical context for morning note generation.

    This is the PRIMARY tool for standard morning note workflow.
    Returns consistent, typed output optimized for LLM reasoning.

    Args:
        session_date: Reference date (YYYY-MM-DD), defaults to today
        lookback_days: How far back to look for context
        db_path: Optional custom database path

    Returns:
        HistoricalContext with recent sessions, streaks, events, and themes

    Example:
        >>> ctx = get_historical_context()
        >>> print(f"5-day SPX: {ctx.spx_5d_return}%")
        >>> print(f"Notable streaks: {[s.sector for s in ctx.sector_streaks]}")
        >>> print(f"Yesterday's theme: {ctx.yesterday_primary_theme}")
    """
    conn = get_db_connection(db_path)
    ref_date = session_date or date.today().isoformat()

    try:
        # Get recent sessions
        recent_sessions = _get_recent_sessions(conn, ref_date, limit=5)

        # Get sector streaks
        sector_streaks = _get_sector_streaks(conn, ref_date)

        # Get recent events
        recent_events = _get_recent_events(conn, ref_date, lookback_days)

        # Get active thematic regimes
        active_regimes = _get_active_regimes(conn, ref_date)

        # Get yesterday's themes
        yesterday_themes = _get_yesterday_themes(conn, ref_date)

        return HistoricalContext(
            as_of=datetime.now(),
            recent_sessions=recent_sessions,
            sector_streaks=sector_streaks,
            recent_events=recent_events,
            active_regimes=active_regimes,
            yesterday_primary_theme=yesterday_themes.get("primary"),
            yesterday_secondary_themes=yesterday_themes.get("secondary", []),
        )
    finally:
        conn.close()


def get_sector_streaks(
    session_date: Optional[str] = None,
    min_streak: int = 3,
    db_path: Optional[Path] = None,
) -> List[SectorStreak]:
    """Get current sector leadership/laggard streaks.

    Args:
        session_date: Reference date
        min_streak: Minimum streak length to include
        db_path: Optional database path

    Returns:
        List of SectorStreak for sectors with active streaks
    """
    conn = get_db_connection(db_path)
    ref_date = session_date or date.today().isoformat()

    try:
        return _get_sector_streaks(conn, ref_date, min_streak)
    finally:
        conn.close()


def get_yesterday_themes(
    session_date: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Get themes from the previous note for continuity.

    Returns:
        Dict with 'primary' theme and 'secondary' themes list
    """
    conn = get_db_connection(db_path)
    ref_date = session_date or date.today().isoformat()

    try:
        return _get_yesterday_themes(conn, ref_date)
    finally:
        conn.close()


# =============================================================================
# EXPLORATORY TOOLS (Flexible Querying)
# =============================================================================

def query_sessions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_spx_change: Optional[float] = None,
    max_spx_change: Optional[float] = None,
    min_breadth_spread: Optional[float] = None,
    max_breadth_spread: Optional[float] = None,
    session_character: Optional[str] = None,
    order_by: str = "session_date DESC",
    limit: int = 50,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Flexible session history query for exploratory analysis.

    Use this to dive deeper into patterns and trends.

    Args:
        start_date: Filter sessions after this date
        end_date: Filter sessions before this date
        min_spx_change: Minimum SPX change %
        max_spx_change: Maximum SPX change %
        min_breadth_spread: Minimum breadth spread
        max_breadth_spread: Maximum breadth spread
        session_character: Filter by character (e.g., "rotation", "risk-off")
        order_by: SQL ORDER BY clause
        limit: Maximum results

    Returns:
        List of session dicts with all available fields

    Examples:
        # Find all sessions with narrow leadership
        >>> sessions = query_sessions(min_breadth_spread=0.5)

        # Find big down days
        >>> sessions = query_sessions(max_spx_change=-1.0)

        # Find rotation days
        >>> sessions = query_sessions(session_character="rotation")
    """
    conn = get_db_connection(db_path)

    conditions = []
    params = []

    if start_date:
        conditions.append("session_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("session_date <= ?")
        params.append(end_date)
    if min_spx_change is not None:
        conditions.append("spx_change_pct >= ?")
        params.append(min_spx_change)
    if max_spx_change is not None:
        conditions.append("spx_change_pct <= ?")
        params.append(max_spx_change)
    if min_breadth_spread is not None:
        conditions.append("breadth_spread >= ?")
        params.append(min_breadth_spread)
    if max_breadth_spread is not None:
        conditions.append("breadth_spread <= ?")
        params.append(max_breadth_spread)
    if session_character:
        conditions.append("session_character LIKE ?")
        params.append(f"%{session_character}%")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT * FROM session_snapshots
        WHERE {where_clause}
        ORDER BY {order_by}
        LIMIT ?
    """
    params.append(limit)

    try:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def find_similar_sessions(
    conditions: Dict[str, Any],
    lookback_days: int = 252,
    limit: int = 10,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Find historical sessions matching specified conditions.

    Use for "last time we saw X was..." context.

    Args:
        conditions: Dict of field -> value or operator dict
            Operators: {"gt": 0.5}, {"lt": -0.5}, {"between": [-0.5, 0.5]}, {"like": "rotation"}
        lookback_days: How far back to search
        limit: Maximum results

    Returns:
        List of matching sessions with similarity context

    Examples:
        # Last time breadth was this narrow
        >>> find_similar_sessions({"breadth_spread": {"gt": 0.8}})

        # Big down days with dollar weakness
        >>> find_similar_sessions({
        ...     "spx_change_pct": {"lt": -1.5},
        ...     "dxy_change_pct": {"lt": -0.3}
        ... })

        # Sessions with similar character
        >>> find_similar_sessions({"session_character": {"like": "risk-off"}})
    """
    conn = get_db_connection(db_path)

    cutoff_date = (date.today() - timedelta(days=lookback_days)).isoformat()

    where_parts = ["session_date >= ?"]
    params = [cutoff_date]

    for field, condition in conditions.items():
        if isinstance(condition, dict):
            if "gt" in condition:
                where_parts.append(f"{field} > ?")
                params.append(condition["gt"])
            elif "gte" in condition:
                where_parts.append(f"{field} >= ?")
                params.append(condition["gte"])
            elif "lt" in condition:
                where_parts.append(f"{field} < ?")
                params.append(condition["lt"])
            elif "lte" in condition:
                where_parts.append(f"{field} <= ?")
                params.append(condition["lte"])
            elif "between" in condition:
                where_parts.append(f"{field} BETWEEN ? AND ?")
                params.extend(condition["between"])
            elif "like" in condition:
                where_parts.append(f"{field} LIKE ?")
                params.append(f"%{condition['like']}%")
        else:
            # Exact match
            where_parts.append(f"{field} = ?")
            params.append(condition)

    query = f"""
        SELECT *,
            julianday('now') - julianday(session_date) as days_ago
        FROM session_snapshots
        WHERE {" AND ".join(where_parts)}
        ORDER BY session_date DESC
        LIMIT ?
    """
    params.append(limit)

    try:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def query_sector_history(
    sector: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_rvol: Optional[float] = None,
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Query sector performance history for trend analysis.

    Args:
        sector: Sector ticker (e.g., "XLK", "XLF")
        start_date: Start of date range
        end_date: End of date range
        min_rvol: Minimum relative volume filter
        limit: Maximum results

    Returns:
        List of daily sector performance records

    Examples:
        # XLK performance over last month
        >>> query_sector_history("XLK", start_date="2024-11-17")

        # High conviction XLF days
        >>> query_sector_history("XLF", min_rvol=1.5)
    """
    conn = get_db_connection(db_path)

    conditions = ["sector = ?"]
    params = [sector]

    if start_date:
        conditions.append("session_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("session_date <= ?")
        params.append(end_date)
    if min_rvol is not None:
        conditions.append("rvol >= ?")
        params.append(min_rvol)

    query = f"""
        SELECT * FROM sector_daily
        WHERE {" AND ".join(conditions)}
        ORDER BY session_date DESC
        LIMIT ?
    """
    params.append(limit)

    try:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def query_adr_history(
    adr_ticker: Optional[str] = None,
    sector: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_rvol: Optional[float] = None,
    min_change: Optional[float] = None,
    max_change: Optional[float] = None,
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Query ADR performance history for Japan read-through analysis.

    Args:
        adr_ticker: Specific ADR (e.g., "MUFG US Equity")
        sector: ADR sector (e.g., "banks", "semiconductors")
        start_date: Start of date range
        end_date: End of date range
        min_rvol: Minimum relative volume
        min_change: Minimum change %
        max_change: Maximum change %
        limit: Maximum results

    Returns:
        List of daily ADR performance records

    Examples:
        # MUFG history
        >>> query_adr_history(adr_ticker="MUFG US Equity")

        # Bank ADRs with high volume
        >>> query_adr_history(sector="banks", min_rvol=2.0)

        # Big moves in semis
        >>> query_adr_history(sector="semiconductors", min_change=3.0)
    """
    conn = get_db_connection(db_path)

    conditions = []
    params = []

    if adr_ticker:
        conditions.append("adr_ticker = ?")
        params.append(adr_ticker)
    if sector:
        conditions.append("sector = ?")
        params.append(sector)
    if start_date:
        conditions.append("session_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("session_date <= ?")
        params.append(end_date)
    if min_rvol is not None:
        conditions.append("rvol >= ?")
        params.append(min_rvol)
    if min_change is not None:
        conditions.append("change_pct >= ?")
        params.append(min_change)
    if max_change is not None:
        conditions.append("change_pct <= ?")
        params.append(max_change)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT * FROM adr_daily
        WHERE {where_clause}
        ORDER BY session_date DESC
        LIMIT ?
    """
    params.append(limit)

    try:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_volume_trends(
    ticker: str,
    weeks: int = 12,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Get weekly volume trends for accumulation/distribution analysis.

    Args:
        ticker: Security ticker
        weeks: Number of weeks to analyze

    Returns:
        Dict with weekly data, trend metrics, and pattern classification

    Example:
        >>> trends = get_volume_trends("6506 JP Equity")
        >>> print(f"Volume trend: {trends['trend_direction']}")
        >>> print(f"Recent vs avg: {trends['recent_vs_avg_pct']}%")
    """
    conn = get_db_connection(db_path)

    query = """
        SELECT * FROM weekly_aggregates
        WHERE ticker = ?
        ORDER BY week_ending DESC
        LIMIT ?
    """

    try:
        cursor = conn.execute(query, [ticker, weeks])
        rows = [dict(row) for row in cursor.fetchall()]

        if not rows:
            return {"ticker": ticker, "weeks": [], "error": "No data found"}

        # Calculate trend metrics
        volumes = [r["total_volume"] for r in rows if r["total_volume"]]

        if len(volumes) >= 4:
            recent_avg = sum(volumes[:4]) / 4
            older_avg = sum(volumes[4:]) / len(volumes[4:]) if len(volumes) > 4 else recent_avg
            trend_pct = ((recent_avg / older_avg) - 1) * 100 if older_avg > 0 else 0
        else:
            trend_pct = 0

        return {
            "ticker": ticker,
            "weeks": rows,
            "total_weeks": len(rows),
            "recent_4w_avg_volume": recent_avg if len(volumes) >= 4 else None,
            "trend_vs_prior_pct": round(trend_pct, 1),
            "trend_direction": "accelerating" if trend_pct > 10 else "decelerating" if trend_pct < -10 else "stable",
        }
    finally:
        conn.close()


def get_event_history(
    event_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Query historical event markers.

    Args:
        event_type: Filter by event type (e.g., "extreme_breadth", "sector_leadership_streak")
        start_date: Start of date range
        end_date: End of date range
        limit: Maximum results

    Returns:
        List of event marker records

    Examples:
        # All breadth extremes
        >>> get_event_history(event_type="extreme_breadth")

        # Recent volume surges
        >>> get_event_history(event_type="volume_extreme", start_date="2024-12-01")
    """
    conn = get_db_connection(db_path)

    conditions = []
    params = []

    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if start_date:
        conditions.append("session_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("session_date <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT *,
            julianday('now') - julianday(session_date) as days_ago
        FROM event_markers
        WHERE {where_clause}
        ORDER BY session_date DESC
        LIMIT ?
    """
    params.append(limit)

    try:
        cursor = conn.execute(query, params)
        rows = []
        for row in cursor.fetchall():
            r = dict(row)
            # Parse JSON metadata
            if r.get("metadata"):
                try:
                    r["metadata"] = json.loads(r["metadata"])
                except (json.JSONDecodeError, ValueError):
                    pass
            rows.append(r)
        return rows
    finally:
        conn.close()


def run_custom_query(
    query: str,
    params: Optional[List[Any]] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Run a custom SQL query for advanced exploration.

    Use with caution - for ad-hoc analysis only.

    Args:
        query: SQL SELECT query
        params: Query parameters

    Returns:
        List of result dicts

    Example:
        >>> results = run_custom_query('''
        ...     SELECT sector, AVG(change_pct) as avg_return, COUNT(*) as days
        ...     FROM sector_daily
        ...     WHERE session_date >= date('now', '-30 days')
        ...     GROUP BY sector
        ...     ORDER BY avg_return DESC
        ... ''')
    """
    if not query.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")

    conn = get_db_connection(db_path)

    try:
        cursor = conn.execute(query, params or [])
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# =============================================================================
# INTERNAL HELPER FUNCTIONS
# =============================================================================

def _get_recent_sessions(
    conn: sqlite3.Connection,
    ref_date: str,
    limit: int = 5,
) -> List[SessionSummary]:
    """Get recent session summaries."""
    query = """
        SELECT
            s.session_date,
            s.spx_change_pct,
            s.breadth_spread,
            s.nasdaq_change_pct - s.spx_change_pct as nasdaq_vs_spx,
            s.russell_change_pct - s.spx_change_pct as russell_vs_spx,
            s.session_character,
            n.primary_theme
        FROM session_snapshots s
        LEFT JOIN notes_archive n ON s.session_date = n.session_date
        WHERE s.session_date < ?
        ORDER BY s.session_date DESC
        LIMIT ?
    """

    cursor = conn.execute(query, [ref_date, limit])
    sessions = []

    for row in cursor.fetchall():
        sessions.append(SessionSummary(
            session_date=row["session_date"],
            spx_change_pct=row["spx_change_pct"] or 0,
            breadth_spread=row["breadth_spread"] or 0,
            nasdaq_vs_spx=row["nasdaq_vs_spx"],
            russell_vs_spx=row["russell_vs_spx"],
            session_character=row["session_character"],
            primary_theme=row["primary_theme"],
        ))

    return sessions


def _get_sector_streaks(
    conn: sqlite3.Connection,
    ref_date: str,
    min_streak: int = 3,
) -> List[SectorStreak]:
    """Calculate current sector streaks."""
    # Get sector names mapping
    sector_names = {
        "XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
        "XLV": "Healthcare", "XLP": "Consumer Staples", "XLI": "Industrials",
        "XLB": "Materials", "XLRE": "Real Estate", "XLU": "Utilities",
        "XLC": "Communication Services", "XLY": "Consumer Discretionary",
    }

    # Get recent sector performance
    query = """
        SELECT sector, session_date, rank, change_pct
        FROM sector_daily
        WHERE session_date <= ?
        ORDER BY session_date DESC
        LIMIT 220  -- ~20 days * 11 sectors
    """

    cursor = conn.execute(query, [ref_date])
    rows = cursor.fetchall()

    # Group by sector and date
    sector_history: Dict[str, List[Dict]] = {}
    for row in rows:
        sector = row["sector"]
        if sector not in sector_history:
            sector_history[sector] = []
        sector_history[sector].append({
            "date": row["session_date"],
            "rank": row["rank"],
            "change_pct": row["change_pct"],
        })

    streaks = []

    for sector, history in sector_history.items():
        if not history:
            continue

        # Check for leader streak (rank <= 3)
        leader_streak = 0
        leader_return = 0
        leader_ranks = []
        for day in history:
            if day["rank"] and day["rank"] <= 3:
                leader_streak += 1
                leader_return += day["change_pct"] or 0
                leader_ranks.append(day["rank"])
            else:
                break

        if leader_streak >= min_streak:
            streaks.append(SectorStreak(
                sector=sector,
                name=sector_names.get(sector, sector),
                streak_type="leader",
                streak_days=leader_streak,
                cumulative_return_pct=round(leader_return, 2),
                avg_rank=round(sum(leader_ranks) / len(leader_ranks), 1),
            ))

        # Check for laggard streak (rank >= 9 for 11 sectors)
        laggard_streak = 0
        laggard_return = 0
        laggard_ranks = []
        for day in history:
            if day["rank"] and day["rank"] >= 9:
                laggard_streak += 1
                laggard_return += day["change_pct"] or 0
                laggard_ranks.append(day["rank"])
            else:
                break

        if laggard_streak >= min_streak:
            streaks.append(SectorStreak(
                sector=sector,
                name=sector_names.get(sector, sector),
                streak_type="laggard",
                streak_days=laggard_streak,
                cumulative_return_pct=round(laggard_return, 2),
                avg_rank=round(sum(laggard_ranks) / len(laggard_ranks), 1),
            ))

    return sorted(streaks, key=lambda s: s.streak_days, reverse=True)


def _get_recent_events(
    conn: sqlite3.Connection,
    ref_date: str,
    lookback_days: int = 20,
) -> List[ExtremeEvent]:
    """Get recent notable events."""
    cutoff = (datetime.strptime(ref_date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    query = """
        SELECT
            event_type,
            session_date,
            event_description,
            metadata,
            julianday(?) - julianday(session_date) as days_ago
        FROM event_markers
        WHERE session_date >= ? AND session_date < ?
        ORDER BY session_date DESC
        LIMIT 20
    """

    cursor = conn.execute(query, [ref_date, cutoff, ref_date])
    events = []

    for row in cursor.fetchall():
        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, ValueError):
                pass

        events.append(ExtremeEvent(
            event_type=row["event_type"],
            event_date=row["session_date"],
            days_ago=int(row["days_ago"]),
            description=row["event_description"] or "",
            metadata=metadata,
        ))

    return events


def _get_active_regimes(
    conn: sqlite3.Connection,
    ref_date: str,
) -> List[ThematicRegime]:
    """Get currently active thematic regimes."""
    query = """
        SELECT
            theme,
            regime,
            start_date,
            trigger_event,
            julianday(?) - julianday(start_date) as days_active
        FROM thematic_regimes
        WHERE end_date IS NULL OR end_date >= ?
        ORDER BY start_date DESC
    """

    cursor = conn.execute(query, [ref_date, ref_date])
    regimes = []

    for row in cursor.fetchall():
        regimes.append(ThematicRegime(
            theme=row["theme"],
            regime=row["regime"],
            start_date=row["start_date"],
            days_active=int(row["days_active"]),
            trigger_event=row["trigger_event"],
        ))

    return regimes


def _get_yesterday_themes(
    conn: sqlite3.Connection,
    ref_date: str,
) -> Dict[str, Any]:
    """Get themes from the previous session's note."""
    query = """
        SELECT primary_theme, secondary_themes
        FROM notes_archive
        WHERE session_date < ?
        ORDER BY session_date DESC
        LIMIT 1
    """

    cursor = conn.execute(query, [ref_date])
    row = cursor.fetchone()

    if not row:
        return {"primary": None, "secondary": []}

    secondary = []
    if row["secondary_themes"]:
        try:
            secondary = json.loads(row["secondary_themes"])
        except (json.JSONDecodeError, ValueError):
            pass

    return {
        "primary": row["primary_theme"],
        "secondary": secondary,
    }

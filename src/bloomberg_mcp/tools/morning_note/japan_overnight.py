"""Japan overnight snapshot tool for morning note generation.

Fetches Japan-relevant data from overnight US session:
- Nikkei futures and EWJ for risk tone
- Japan ADRs with sector groupings and RVOL (dynamic via EQS screen)
- Japan equity watchlist
"""

from datetime import datetime
from typing import Dict, List, Optional

from ..reference import get_reference_data
from .config import (
    JAPAN_PROXIES,
    JAPAN_WATCHLIST,
    INDEX_FIELDS,
    JP_EQUITY_FIELDS,
)
from .models import (
    JapanOvernightSnapshot,
    JapanProxySnapshot,
    IndexSnapshot,
    PriceData,
    JPEquitySnapshot,
)
from .adr_screen import get_adr_sector_summary


def get_japan_overnight_snapshot() -> JapanOvernightSnapshot:
    """Get complete Japan-relevant data for morning note.

    Fetches Nikkei futures, EWJ, Japan ADRs, and Japan equity watchlist
    with all derived metrics (implied moves, divergences, RVOL).

    ADRs are fetched from the Japan_Liquid_ADRs EQS screen which filters
    for >$10M avg daily value traded.

    Returns:
        JapanOvernightSnapshot with complete structured data for LLM reasoning.

    Example:
        >>> snapshot = get_japan_overnight_snapshot()
        >>> print(f"Futures implied: {snapshot.proxies.futures_implied_move_pct}%")
        >>> print(f"Banks: {snapshot.adr_sectors['banks'].avg_change_pct}%")
        >>> print(f"High RVOL: {snapshot.high_rvol_adrs}")
    """
    # Fetch all data
    proxy_data = _fetch_proxy_data()
    adr_data = get_adr_sector_summary()
    watchlist_data = _fetch_watchlist_data()

    return JapanOvernightSnapshot(
        as_of=datetime.now(),
        proxies=proxy_data,
        adr_sectors=adr_data,
        watchlist=watchlist_data,
    )


def _fetch_proxy_data() -> JapanProxySnapshot:
    """Fetch Nikkei, TOPIX, and EWJ data."""
    # Get all proxy tickers
    tickers = [p.ticker for p in JAPAN_PROXIES.values()]

    # Fetch data - EWJ needs volume fields too
    fields = INDEX_FIELDS + ["VOLUME", "VOLUME_AVG_20D"]
    results = get_reference_data(tickers, fields)

    # Helper to build IndexSnapshot
    def get_index(key: str) -> IndexSnapshot:
        proxy_def = JAPAN_PROXIES[key]
        sec_data = next((r for r in results if r.security == proxy_def.ticker), None)
        if sec_data and sec_data.fields:
            f = sec_data.fields
            return IndexSnapshot(
                ticker=proxy_def.ticker,
                name=proxy_def.name,
                price=PriceData(
                    last=f.get("PX_LAST", 0),
                    change_pct=f.get("CHG_PCT_1D", 0),
                    open=f.get("PX_OPEN"),
                    high=f.get("PX_HIGH"),
                    low=f.get("PX_LOW"),
                ),
                volume=f.get("VOLUME"),
            )
        return IndexSnapshot(
            ticker=proxy_def.ticker,
            name=proxy_def.name,
            price=PriceData(last=0, change_pct=0),
        )

    return JapanProxySnapshot(
        nikkei_cash=get_index("nikkei_cash"),
        nikkei_futures=get_index("nikkei_futures"),
        topix=get_index("topix"),
        ewj=get_index("ewj"),
    )


def _fetch_watchlist_data() -> Dict[str, List[JPEquitySnapshot]]:
    """Fetch Japan equity watchlist data."""
    # Collect all watchlist tickers
    all_tickers = []
    ticker_to_equity = {}

    for theme, equities in JAPAN_WATCHLIST.items():
        for eq in equities:
            all_tickers.append(eq.ticker)
            ticker_to_equity[eq.ticker] = eq

    # Fetch data
    results = get_reference_data(all_tickers, JP_EQUITY_FIELDS)

    # Group by theme
    watchlist: Dict[str, List[JPEquitySnapshot]] = {theme: [] for theme in JAPAN_WATCHLIST.keys()}

    for sec_data in results:
        if not sec_data.fields:
            continue

        f = sec_data.fields
        ticker = sec_data.security
        eq_def = ticker_to_equity.get(ticker)

        if not eq_def:
            continue

        snapshot = JPEquitySnapshot(
            ticker=ticker,
            code=eq_def.code,
            name=eq_def.name,
            theme=eq_def.theme,
            last=f.get("PX_LAST", 0),
            change_pct=round(f.get("CHG_PCT_1D", 0), 2),
            gics_sector=f.get("GICS_SECTOR_NAME"),
        )
        watchlist[eq_def.theme].append(snapshot)

    return watchlist


def get_japan_watchlist() -> Dict[str, List[JPEquitySnapshot]]:
    """Get just the Japan equity watchlist.

    Lighter-weight call for when you only need watchlist data.

    Returns:
        Dict mapping theme -> list of JPEquitySnapshot
    """
    return _fetch_watchlist_data()

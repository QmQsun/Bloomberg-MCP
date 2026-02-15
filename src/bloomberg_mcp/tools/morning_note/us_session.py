"""US Session snapshot tool for morning note generation.

Fetches complete US market data in efficient batches and structures it
for LLM consumption with derived metrics and context.
"""

from datetime import datetime
from typing import Dict, List, Optional

from ..reference import get_reference_data
from .config import (
    US_INDEXES,
    SECTOR_ETFS,
    INDUSTRY_ETFS,
    MACRO_FX,
    MACRO_RATES,
    MACRO_COMMODITIES,
    MACRO_VOLATILITY,
    PRICE_FIELDS,
    VOLUME_FIELDS,
    MACRO_FIELDS,
)
from .models import (
    USSessionSnapshot,
    IndexSnapshot,
    PriceData,
    VolumeData,
    BreadthContext,
    SectorSnapshot,
    IndustrySnapshot,
    MacroSnapshot,
    MacroInstrument,
    YieldCurve,
)


def get_us_session_snapshot(session_date: Optional[str] = None) -> USSessionSnapshot:
    """Get complete US session data for morning note generation.

    Fetches index performance, sector rankings, industry leadership,
    and macro data in efficient batches. All derived metrics (breadth
    spreads, rankings, relative volume) are pre-computed.

    Args:
        session_date: Optional date string (YYYY-MM-DD). If not provided,
                     uses current date (data reflects last available session).

    Returns:
        USSessionSnapshot with complete structured data for LLM reasoning.

    Example:
        >>> snapshot = get_us_session_snapshot()
        >>> print(f"SPX: {snapshot.indexes['spx'].price.change_pct}%")
        >>> print(f"Breadth: {snapshot.breadth.spread}")
        >>> print(f"Leaders: {[s.name for s in snapshot.sector_leaders]}")
    """
    # Use current date if not specified
    if session_date is None:
        session_date = datetime.now().strftime("%Y-%m-%d")

    # Fetch all data in batches
    index_data = _fetch_index_data()
    sector_data = _fetch_sector_data()
    industry_data = _fetch_industry_data()
    macro_data = _fetch_macro_data()

    # Build structured response
    return USSessionSnapshot(
        as_of=datetime.now(),
        session_date=session_date,
        indexes=index_data["indexes"],
        breadth=index_data["breadth"],
        sectors=sector_data,
        industry_etfs=industry_data,
        macro=macro_data,
    )


def _fetch_index_data() -> Dict:
    """Fetch and structure index data with breadth context."""
    # Get all index tickers
    tickers = [idx.ticker for idx in US_INDEXES.values()]

    # Fetch data
    fields = PRICE_FIELDS + ["VOLUME"]
    results = get_reference_data(tickers, fields)

    # Build index snapshots
    indexes: Dict[str, IndexSnapshot] = {}
    for key, idx_def in US_INDEXES.items():
        sec_data = next((r for r in results if r.security == idx_def.ticker), None)
        if sec_data and sec_data.fields:
            f = sec_data.fields
            indexes[key] = IndexSnapshot(
                ticker=idx_def.ticker,
                name=idx_def.name,
                price=PriceData(
                    last=f.get("PX_LAST", 0),
                    change_pct=f.get("CHG_PCT_1D", 0),
                    open=f.get("PX_OPEN"),
                    high=f.get("PX_HIGH"),
                    low=f.get("PX_LOW"),
                ),
                volume=f.get("VOLUME"),
            )

    # Compute breadth context
    spx_chg = indexes["spx"].price.change_pct if "spx" in indexes else 0
    spw_chg = indexes["spw"].price.change_pct if "spw" in indexes else 0
    nasdaq_chg = indexes["nasdaq"].price.change_pct if "nasdaq" in indexes else 0
    russell_chg = indexes["russell"].price.change_pct if "russell" in indexes else 0

    breadth = BreadthContext(
        spx_change_pct=round(spx_chg, 2),
        spw_change_pct=round(spw_chg, 2),
        spread=round(spx_chg - spw_chg, 2),
        nasdaq_vs_spx=round(nasdaq_chg - spx_chg, 2),
        russell_vs_spx=round(russell_chg - spx_chg, 2),
    )

    return {"indexes": indexes, "breadth": breadth}


def _fetch_sector_data() -> List[SectorSnapshot]:
    """Fetch and structure sector ETF data with rankings."""
    # Get all sector tickers
    tickers = [s.ticker for s in SECTOR_ETFS]

    # Fetch data
    fields = ["PX_LAST", "CHG_PCT_1D"] + VOLUME_FIELDS
    results = get_reference_data(tickers, fields)

    # Build sector snapshots
    sectors: List[SectorSnapshot] = []
    for sec_def in SECTOR_ETFS:
        sec_data = next((r for r in results if r.security == sec_def.ticker), None)
        if sec_data and sec_data.fields:
            f = sec_data.fields
            volume_data = None
            if f.get("VOLUME") and f.get("VOLUME_AVG_20D"):
                volume_data = VolumeData(
                    volume=f["VOLUME"],
                    avg_20d=f["VOLUME_AVG_20D"],
                )
            sectors.append(SectorSnapshot(
                ticker=sec_def.ticker,
                name=sec_def.name,
                change_pct=round(f.get("CHG_PCT_1D", 0), 2),
                rank=0,  # Will be set after sorting
                total_sectors=len(SECTOR_ETFS),
                volume=volume_data,
            ))

    # Sort by performance and assign ranks
    sectors.sort(key=lambda s: s.change_pct, reverse=True)
    for i, sector in enumerate(sectors):
        sector.rank = i + 1

    return sectors


def _fetch_industry_data() -> Dict[str, List[IndustrySnapshot]]:
    """Fetch and structure industry ETF data by theme."""
    # Collect all tickers across themes
    all_tickers = []
    ticker_to_theme = {}
    ticker_to_name = {}

    for theme, etfs in INDUSTRY_ETFS.items():
        for etf in etfs:
            all_tickers.append(etf.ticker)
            ticker_to_theme[etf.ticker] = theme
            ticker_to_name[etf.ticker] = etf.name

    # Fetch data
    fields = ["PX_LAST", "CHG_PCT_1D"] + VOLUME_FIELDS
    results = get_reference_data(all_tickers, fields)

    # Build grouped structure
    industry_etfs: Dict[str, List[IndustrySnapshot]] = {theme: [] for theme in INDUSTRY_ETFS.keys()}

    for sec_data in results:
        if sec_data.fields:
            f = sec_data.fields
            ticker = sec_data.security
            theme = ticker_to_theme.get(ticker)

            # Skip securities that aren't in our theme mapping
            if theme is None:
                continue

            name = ticker_to_name.get(ticker, ticker)

            volume_data = None
            if f.get("VOLUME") and f.get("VOLUME_AVG_20D"):
                volume_data = VolumeData(
                    volume=f["VOLUME"],
                    avg_20d=f["VOLUME_AVG_20D"],
                )

            snapshot = IndustrySnapshot(
                ticker=ticker,
                name=name,
                theme=theme,
                change_pct=round(f.get("CHG_PCT_1D", 0), 2),
                volume=volume_data,
            )
            industry_etfs[theme].append(snapshot)

    return industry_etfs


def _fetch_macro_data() -> MacroSnapshot:
    """Fetch and structure macro data (FX, rates, commodities, volatility)."""
    # Collect all macro tickers
    fx_tickers = {k: v.ticker for k, v in MACRO_FX.items()}
    rate_tickers = {k: v.ticker for k, v in MACRO_RATES.items()}
    commodity_tickers = {k: v.ticker for k, v in MACRO_COMMODITIES.items()}
    volatility_tickers = {k: v.ticker for k, v in MACRO_VOLATILITY.items()}

    all_tickers = (
        list(fx_tickers.values()) +
        list(rate_tickers.values()) +
        list(commodity_tickers.values()) +
        list(volatility_tickers.values())
    )

    # Fetch data
    results = get_reference_data(all_tickers, MACRO_FIELDS)

    # Helper to extract MacroInstrument
    def get_macro(ticker: str, name: str) -> MacroInstrument:
        sec_data = next((r for r in results if r.security == ticker), None)
        if sec_data and sec_data.fields:
            f = sec_data.fields
            return MacroInstrument(
                ticker=ticker,
                name=name,
                last=f.get("PX_LAST", 0),
                change_pct=round(f.get("CHG_PCT_1D", 0), 2),
                open=f.get("PX_OPEN"),
            )
        return MacroInstrument(ticker=ticker, name=name, last=0, change_pct=0)

    # Build FX
    dxy = get_macro(MACRO_FX["dxy"].ticker, MACRO_FX["dxy"].name)
    usdjpy = get_macro(MACRO_FX["usdjpy"].ticker, MACRO_FX["usdjpy"].name)
    eurjpy = get_macro(MACRO_FX["eurjpy"].ticker, MACRO_FX["eurjpy"].name) if "eurjpy" in MACRO_FX else None

    # Build Rates
    us_10y_data = next((r for r in results if r.security == MACRO_RATES["us_10y"].ticker), None)
    us_2y_data = next((r for r in results if r.security == MACRO_RATES["us_2y"].ticker), None)
    jp_10y_data = next((r for r in results if r.security == MACRO_RATES["jp_10y"].ticker), None)

    yields = YieldCurve(
        us_10y=us_10y_data.fields.get("PX_LAST", 0) if us_10y_data else 0,
        us_2y=us_2y_data.fields.get("PX_LAST", 0) if us_2y_data else 0,
        jp_10y=jp_10y_data.fields.get("PX_LAST", 0) if jp_10y_data else 0,
    )

    us_10y_change = us_10y_data.fields.get("CHG_PCT_1D", 0) if us_10y_data else 0
    jp_10y_change = jp_10y_data.fields.get("CHG_PCT_1D", 0) if jp_10y_data else 0

    # Build Commodities
    wti = get_macro(MACRO_COMMODITIES["wti"].ticker, MACRO_COMMODITIES["wti"].name)
    brent = get_macro(MACRO_COMMODITIES["brent"].ticker, MACRO_COMMODITIES["brent"].name) if "brent" in MACRO_COMMODITIES else None
    gold = get_macro(MACRO_COMMODITIES["gold"].ticker, MACRO_COMMODITIES["gold"].name)

    # Build Volatility (Beta feature)
    vix = get_macro(MACRO_VOLATILITY["vix"].ticker, MACRO_VOLATILITY["vix"].name) if "vix" in MACRO_VOLATILITY else None

    return MacroSnapshot(
        dxy=dxy,
        usdjpy=usdjpy,
        eurjpy=eurjpy,
        yields=yields,
        us_10y_change_pct=round(us_10y_change, 2),
        jp_10y_change_pct=round(jp_10y_change, 2),
        wti=wti,
        brent=brent,
        gold=gold,
        vix=vix,
    )

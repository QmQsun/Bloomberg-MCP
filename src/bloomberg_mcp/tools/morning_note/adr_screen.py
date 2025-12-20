"""Dynamic ADR fetching via EQS screen.

This module fetches liquid Japan ADRs from the Bloomberg EQS screen
and enriches them with real-time RVOL data.

The screen (Japan_Liquid_ADRs) filters for:
- Japan domiciled companies
- US exchange listed (ADRs)
- Average daily value traded > $10M USD

This provides a dynamic universe that adapts as liquidity changes.
"""

from datetime import datetime
from typing import Dict, List, Optional

from ..reference import get_reference_data
from ..screening import run_screen
from .config import (
    JAPAN_ADR_SCREEN,
    GICS_TO_SECTOR_MAP,
    GICS_SUBIND_TO_SECTOR_MAP,
)
from .models import (
    ADRSnapshot,
    ADRSectorSummary,
    VolumeData,
)


def get_liquid_adrs_from_screen() -> List[Dict]:
    """Fetch liquid Japan ADRs from EQS screen.

    Returns:
        List of ADR data dicts from the screen

    Raises:
        RuntimeError: If screen fails or returns no data

    Example:
        >>> adrs = get_liquid_adrs_from_screen()
        >>> print(f"Got {len(adrs)} ADRs")
    """
    result = run_screen(
        screen_name=JAPAN_ADR_SCREEN.name,
        screen_type=JAPAN_ADR_SCREEN.screen_type,
    )

    if not result or not result.securities:
        raise RuntimeError(f"EQS screen '{JAPAN_ADR_SCREEN.name}' returned no data")

    return result.field_data


def classify_adr_sector(
    gics_sector: Optional[str],
    gics_subind: Optional[str],
) -> str:
    """Classify ADR into our sector categories.

    Priority:
    1. Sub-industry mapping (most specific)
    2. GICS sector mapping
    3. Default to "other"

    Args:
        gics_sector: GICS Sector Name
        gics_subind: GICS Sub-Industry Name

    Returns:
        Sector category string
    """
    # Check sub-industry first (most specific)
    if gics_subind and gics_subind in GICS_SUBIND_TO_SECTOR_MAP:
        return GICS_SUBIND_TO_SECTOR_MAP[gics_subind]

    # Fall back to GICS sector
    if gics_sector and gics_sector in GICS_TO_SECTOR_MAP:
        return GICS_TO_SECTOR_MAP[gics_sector]

    return "other"


def build_adr_snapshots(
    adr_data: List[Dict],
    enrich_with_rvol: bool = True,
) -> Dict[str, ADRSectorSummary]:
    """Build ADRSnapshot models grouped by sector.

    Args:
        adr_data: Raw ADR data from screen
        enrich_with_rvol: Fetch additional RVOL data if needed

    Returns:
        Dict mapping sector -> ADRSectorSummary
    """
    # If we need to enrich with current volume data
    if enrich_with_rvol:
        # Screen returns tickers like "TOELY US" but Bloomberg API requires "TOELY US Equity"
        tickers = []
        for d in adr_data:
            raw_ticker = d.get("security") or d.get("Ticker")
            if raw_ticker and not raw_ticker.endswith(" Equity"):
                tickers.append(f"{raw_ticker} Equity")
            else:
                tickers.append(raw_ticker)
        vol_data = get_reference_data(tickers, ["VOLUME", "VOLUME_AVG_20D", "CHG_PCT_1D", "PX_OPEN", "PX_LAST"])
        vol_map = {v.security: v.fields for v in vol_data if v.fields}
    else:
        vol_map = {}

    # Group by sector
    adr_by_sector: Dict[str, List[ADRSnapshot]] = {}

    for adr in adr_data:
        # Get ticker in standard format
        ticker = adr.get("security") or f"{adr.get('Ticker')} US Equity"
        if not ticker.endswith(" Equity"):
            ticker = f"{ticker} Equity"

        # Classify sector
        sector = classify_adr_sector(
            gics_sector=adr.get("GICS Sector"),
            gics_subind=adr.get("GICS SubInd Name"),
        )

        # Get volume data
        vol_fields = vol_map.get(ticker, {})
        volume = vol_fields.get("VOLUME") or adr.get("VOLUME")
        vol_avg = vol_fields.get("VOLUME_AVG_20D") or adr.get("Average Volume:D-20")

        volume_data = None
        if volume and vol_avg and vol_avg > 0:
            volume_data = VolumeData(volume=float(volume), avg_20d=float(vol_avg))

        # Get underlying ticker
        und_tkr = adr.get("Und Tkr", "")
        if und_tkr and not und_tkr.endswith(" Equity"):
            und_tkr = f"{und_tkr} JP Equity"

        # Build snapshot
        snapshot = ADRSnapshot(
            adr_ticker=ticker,
            jp_code=und_tkr,
            name=adr.get("Short Name", ""),
            sector=sector,
            last=float(vol_fields.get("PX_LAST") or adr.get("PX_LAST") or 0),
            change_pct=round(float(vol_fields.get("CHG_PCT_1D") or adr.get("CHG_PCT_1D") or 0), 2),
            open=vol_fields.get("PX_OPEN") or adr.get("PX_OPEN"),
            prev_close=adr.get("PX_CLOSE_1D"),
            volume=volume_data,
        )

        if sector not in adr_by_sector:
            adr_by_sector[sector] = []
        adr_by_sector[sector].append(snapshot)

    # Build sector summaries
    result: Dict[str, ADRSectorSummary] = {}
    for sector, adrs in adr_by_sector.items():
        if adrs:
            result[sector] = ADRSectorSummary(sector=sector, adrs=adrs)

    return result


def get_adr_sector_summary() -> Dict[str, ADRSectorSummary]:
    """Get complete ADR sector summary with RVOL.

    This is the main entry point for ADR data in morning notes.
    Uses the Japan_Liquid_ADRs EQS screen for the ADR universe.

    Returns:
        Dict mapping sector -> ADRSectorSummary with all ADRs

    Example:
        >>> sectors = get_adr_sector_summary()
        >>> print(f"Banks avg: {sectors['banks'].avg_change_pct}%")
        >>> print(f"High RVOL: {sectors['banks'].highest_rvol_ticker}")
    """
    adr_data = get_liquid_adrs_from_screen()
    return build_adr_snapshots(adr_data, enrich_with_rvol=True)

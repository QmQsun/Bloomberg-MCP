"""Explore advanced screening patterns using validated Bloomberg fields.

This script tests various screening patterns to identify which ones
produce useful results and should be documented.
"""

from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional
import statistics

from bloomberg_mcp.tools.dynamic_screening import DynamicScreen, FieldSets
from bloomberg_mcp.tools.dynamic_screening.models import SecurityRecord


# =============================================================================
# PATTERN 1: MOMENTUM PERSISTENCE / REVERSAL
# =============================================================================

def explore_momentum_persistence():
    """Find securities with consistent momentum across timeframes."""
    print("\n" + "=" * 70)
    print("PATTERN: Momentum Persistence")
    print("=" * 70)

    result = (
        DynamicScreen("Momentum Persistence")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.MOMENTUM_EXTENDED + FieldSets.RVOL)
        .run()
    )

    persistent_bulls = []
    persistent_bears = []
    reversals = []

    for rec in result:
        d1 = rec.change_pct or 0
        d5 = rec.change_5d or 0
        m1 = rec.change_1m or 0
        m3 = rec.change_3m or 0

        # All positive - persistent bull
        if d1 > 0 and d5 > 0 and m1 > 0 and m3 > 0:
            strength = d1 + d5 + m1 + m3
            persistent_bulls.append((rec, strength))

        # All negative - persistent bear
        elif d1 < 0 and d5 < 0 and m1 < 0 and m3 < 0:
            strength = abs(d1) + abs(d5) + abs(m1) + abs(m3)
            persistent_bears.append((rec, strength))

        # Reversal: short-term opposite to medium-term
        elif (d1 > 1 and m3 < -5) or (d1 < -1 and m3 > 5):
            reversals.append((rec, d1, m3))

    print(f"\nPersistent Bulls ({len(persistent_bulls)}):")
    for rec, strength in sorted(persistent_bulls, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: 1D={rec.change_pct:+.1f}%, 5D={rec.change_5d:+.1f}%, "
              f"1M={rec.change_1m:+.1f}%, 3M={rec.change_3m:+.1f}%")

    print(f"\nPersistent Bears ({len(persistent_bears)}):")
    for rec, strength in sorted(persistent_bears, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: 1D={rec.change_pct:+.1f}%, 5D={rec.change_5d:+.1f}%, "
              f"1M={rec.change_1m:+.1f}%, 3M={rec.change_3m:+.1f}%")

    print(f"\nReversals ({len(reversals)}):")
    for rec, d1, m3 in reversals[:5]:
        direction = "Bounce" if d1 > 0 else "Pullback"
        print(f"  {rec.ticker}: {direction} - 1D={d1:+.1f}% vs 3M={m3:+.1f}%")

    return {"bulls": persistent_bulls, "bears": persistent_bears, "reversals": reversals}


# =============================================================================
# PATTERN 2: VOLUME TREND ANALYSIS
# =============================================================================

def explore_volume_trends():
    """Analyze volume trends across different timeframes."""
    print("\n" + "=" * 70)
    print("PATTERN: Volume Trend Analysis")
    print("=" * 70)

    result = (
        DynamicScreen("Volume Trends")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.VOLUME_EXTENDED + FieldSets.PRICE)
        .run()
    )

    accelerating_volume = []
    decelerating_volume = []
    volume_spikes = []

    for rec in result:
        vol = rec.fields.get("VOLUME") or 0
        avg5 = rec.fields.get("VOLUME_AVG_5D") or 1
        avg10 = rec.fields.get("VOLUME_AVG_10D") or 1
        avg20 = rec.fields.get("VOLUME_AVG_20D") or 1
        avg30 = rec.fields.get("VOLUME_AVG_30D") or 1

        if avg5 == 0 or avg20 == 0:
            continue

        rvol_5d = vol / avg5
        rvol_20d = vol / avg20

        # Volume acceleration: short-term avg > long-term avg
        if avg5 > avg10 > avg20:
            accel = (avg5 / avg20 - 1) * 100
            accelerating_volume.append((rec, accel, rvol_20d))

        # Volume deceleration
        elif avg5 < avg10 < avg20:
            decel = (1 - avg5 / avg20) * 100
            decelerating_volume.append((rec, decel, rvol_20d))

        # Volume spike: today's volume > 2x any average
        if rvol_5d > 2 or rvol_20d > 2:
            volume_spikes.append((rec, rvol_5d, rvol_20d))

    print(f"\nAccelerating Volume ({len(accelerating_volume)}):")
    for rec, accel, rvol in sorted(accelerating_volume, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: 5D avg +{accel:.0f}% vs 20D avg, Today RVOL={rvol:.1f}x")

    print(f"\nVolume Spikes ({len(volume_spikes)}):")
    for rec, rvol5, rvol20 in sorted(volume_spikes, key=lambda x: x[2], reverse=True)[:5]:
        print(f"  {rec.ticker}: RVOL(5D)={rvol5:.1f}x, RVOL(20D)={rvol20:.1f}x, "
              f"Chg={rec.change_pct or 0:+.1f}%")

    return {"accelerating": accelerating_volume, "spikes": volume_spikes}


# =============================================================================
# PATTERN 3: GAP AND INTRADAY RANGE ANALYSIS
# =============================================================================

def explore_gap_analysis():
    """Analyze opening gaps and intraday ranges."""
    print("\n" + "=" * 70)
    print("PATTERN: Gap and Range Analysis")
    print("=" * 70)

    result = (
        DynamicScreen("Gap Analysis")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields([
            "PX_LAST", "PX_OPEN", "PX_HIGH", "PX_LOW", "PX_CLOSE_1D",
            "CHG_PCT_1D", "VOLUME", "VOLUME_AVG_20D"
        ])
        .run()
    )

    gap_ups = []
    gap_downs = []
    wide_ranges = []
    narrow_ranges = []

    for rec in result:
        px_open = rec.fields.get("PX_OPEN") or 0
        px_close_1d = rec.fields.get("PX_CLOSE_1D") or 0
        px_high = rec.fields.get("PX_HIGH") or 0
        px_low = rec.fields.get("PX_LOW") or 0
        px_last = rec.price or 0

        if px_close_1d == 0 or px_low == 0:
            continue

        # Calculate gap
        gap_pct = ((px_open - px_close_1d) / px_close_1d) * 100

        # Calculate intraday range
        intraday_range = ((px_high - px_low) / px_low) * 100

        # Gap fill analysis
        if gap_pct > 0.5:
            gap_filled = px_last <= px_close_1d
            gap_ups.append((rec, gap_pct, gap_filled))
        elif gap_pct < -0.5:
            gap_filled = px_last >= px_close_1d
            gap_downs.append((rec, gap_pct, gap_filled))

        # Range analysis
        if intraday_range > 3:
            wide_ranges.append((rec, intraday_range, rec.change_pct or 0))
        elif intraday_range < 1:
            narrow_ranges.append((rec, intraday_range))

    print(f"\nGap Ups ({len(gap_ups)}):")
    for rec, gap, filled in sorted(gap_ups, key=lambda x: x[1], reverse=True)[:5]:
        status = "FILLED" if filled else "unfilled"
        print(f"  {rec.ticker}: Gap +{gap:.1f}% ({status}), Now {rec.change_pct or 0:+.1f}%")

    print(f"\nGap Downs ({len(gap_downs)}):")
    for rec, gap, filled in sorted(gap_downs, key=lambda x: x[1])[:5]:
        status = "FILLED" if filled else "unfilled"
        print(f"  {rec.ticker}: Gap {gap:.1f}% ({status}), Now {rec.change_pct or 0:+.1f}%")

    print(f"\nWide Ranges ({len(wide_ranges)}):")
    for rec, rng, chg in sorted(wide_ranges, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: Range {rng:.1f}%, Close {chg:+.1f}%")

    return {"gap_ups": gap_ups, "gap_downs": gap_downs, "wide_ranges": wide_ranges}


# =============================================================================
# PATTERN 4: CROSS-SECTIONAL RANKING
# =============================================================================

def explore_cross_sectional_ranking():
    """Rank securities within universe by multiple factors."""
    print("\n" + "=" * 70)
    print("PATTERN: Cross-Sectional Percentile Ranking")
    print("=" * 70)

    result = (
        DynamicScreen("Cross-Sectional")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.SCREENING_FULL)
        .run()
    )

    # Calculate percentile ranks for each factor
    def calculate_percentiles(records, field_getter, higher_is_better=True):
        values = [(rec, field_getter(rec)) for rec in records if field_getter(rec) is not None]
        if not values:
            return {}

        sorted_vals = sorted(values, key=lambda x: x[1], reverse=higher_is_better)
        n = len(sorted_vals)
        return {rec.security: (i + 1) / n * 100 for i, (rec, _) in enumerate(sorted_vals)}

    # Calculate percentiles for each factor
    momentum_pct = calculate_percentiles(result, lambda r: r.change_pct, higher_is_better=True)
    rvol_pct = calculate_percentiles(result, lambda r: r.rvol, higher_is_better=True)
    rsi_pct = calculate_percentiles(result, lambda r: r.rsi, higher_is_better=False)  # Lower RSI = more oversold
    sentiment_pct = calculate_percentiles(result, lambda r: r.sentiment, higher_is_better=True)

    # Composite score
    composite_scores = []
    for rec in result:
        sec = rec.security
        if sec in momentum_pct and sec in rvol_pct:
            score = (
                momentum_pct.get(sec, 50) * 0.3 +
                rvol_pct.get(sec, 50) * 0.3 +
                (100 - rsi_pct.get(sec, 50)) * 0.2 +  # Invert RSI percentile
                sentiment_pct.get(sec, 50) * 0.2
            )
            composite_scores.append((rec, score, momentum_pct.get(sec, 0), rvol_pct.get(sec, 0)))

    print(f"\nTop Composite Scores (Momentum + RVOL + RSI + Sentiment):")
    for rec, score, mom_pct, rvol_pct_val in sorted(composite_scores, key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {rec.ticker}: Score={score:.0f}, MomPct={mom_pct:.0f}, RVOLPct={rvol_pct_val:.0f}")

    return composite_scores


# =============================================================================
# PATTERN 5: VOLATILITY REGIME DETECTION
# =============================================================================

def explore_volatility_regimes():
    """Detect volatility regimes using term structure."""
    print("\n" + "=" * 70)
    print("PATTERN: Volatility Regime Detection")
    print("=" * 70)

    result = (
        DynamicScreen("Vol Regime")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.VOLATILITY + FieldSets.BETA + FieldSets.PRICE)
        .run()
    )

    vol_contango = []      # Short-term vol > long-term vol (stressed)
    vol_backwardation = [] # Long-term vol > short-term vol (calm)
    vol_expanding = []     # Recent vol increasing
    vol_contracting = []   # Recent vol decreasing

    for rec in result:
        v10 = rec.fields.get("VOLATILITY_10D") or 0
        v20 = rec.fields.get("VOLATILITY_20D") or 0
        v30 = rec.fields.get("VOLATILITY_30D") or 0
        v60 = rec.fields.get("VOLATILITY_60D") or 0
        v90 = rec.fields.get("VOLATILITY_90D") or 0

        if v10 == 0 or v90 == 0:
            continue

        # Term structure slope
        slope = (v10 - v90) / v90 * 100

        if v10 > v30 > v90:
            vol_contango.append((rec, slope, v10, v90))
        elif v10 < v30 < v90:
            vol_backwardation.append((rec, abs(slope), v10, v90))

        # Vol trend
        if v10 > v20 > v30:
            vol_expanding.append((rec, v10 - v30))
        elif v10 < v20 < v30:
            vol_contracting.append((rec, v30 - v10))

    print(f"\nVol Contango - Stressed ({len(vol_contango)}):")
    for rec, slope, v10, v90 in sorted(vol_contango, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: 10D={v10:.1f}% vs 90D={v90:.1f}% (slope +{slope:.0f}%)")

    print(f"\nVol Backwardation - Calm ({len(vol_backwardation)}):")
    for rec, slope, v10, v90 in sorted(vol_backwardation, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: 10D={v10:.1f}% vs 90D={v90:.1f}% (slope -{slope:.0f}%)")

    print(f"\nVol Expanding ({len(vol_expanding)}):")
    for rec, diff in sorted(vol_expanding, key=lambda x: x[1], reverse=True)[:5]:
        v10 = rec.fields.get("VOLATILITY_10D") or 0
        print(f"  {rec.ticker}: 10D={v10:.1f}%, expanding by {diff:.1f}pts")

    return {"contango": vol_contango, "backwardation": vol_backwardation}


# =============================================================================
# PATTERN 6: SECTOR-RELATIVE PERFORMANCE
# =============================================================================

def explore_sector_relative():
    """Find securities outperforming or underperforming their sector."""
    print("\n" + "=" * 70)
    print("PATTERN: Sector-Relative Performance")
    print("=" * 70)

    result = (
        DynamicScreen("Sector Relative")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.MOMENTUM + FieldSets.SECTOR + FieldSets.RVOL)
        .run()
    )

    # Calculate sector averages
    sector_data = defaultdict(list)
    for rec in result:
        sector = rec.sector or "Unknown"
        if rec.change_pct is not None:
            sector_data[sector].append(rec.change_pct)

    sector_avgs = {s: statistics.mean(v) for s, v in sector_data.items() if v}

    # Calculate relative performance
    outperformers = []
    underperformers = []

    for rec in result:
        sector = rec.sector or "Unknown"
        chg = rec.change_pct
        if chg is None or sector not in sector_avgs:
            continue

        sector_avg = sector_avgs[sector]
        relative = chg - sector_avg

        if relative > 1:  # Outperforming by > 1%
            outperformers.append((rec, relative, sector_avg))
        elif relative < -1:  # Underperforming by > 1%
            underperformers.append((rec, relative, sector_avg))

    print(f"\nSector Averages:")
    for sector, avg in sorted(sector_avgs.items(), key=lambda x: x[1], reverse=True):
        count = len(sector_data[sector])
        print(f"  {sector}: {avg:+.2f}% ({count} names)")

    print(f"\nOutperformers vs Sector ({len(outperformers)}):")
    for rec, rel, sect_avg in sorted(outperformers, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker} ({rec.sector}): {rec.change_pct:+.1f}% vs sector {sect_avg:+.1f}% "
              f"(+{rel:.1f}% relative)")

    print(f"\nUnderperformers vs Sector ({len(underperformers)}):")
    for rec, rel, sect_avg in sorted(underperformers, key=lambda x: x[1])[:5]:
        print(f"  {rec.ticker} ({rec.sector}): {rec.change_pct:+.1f}% vs sector {sect_avg:+.1f}% "
              f"({rel:.1f}% relative)")

    return {"outperformers": outperformers, "underperformers": underperformers, "sector_avgs": sector_avgs}


# =============================================================================
# PATTERN 7: LIQUIDITY TIERING
# =============================================================================

def explore_liquidity_tiering():
    """Tier securities by liquidity for tradability assessment."""
    print("\n" + "=" * 70)
    print("PATTERN: Liquidity Tiering")
    print("=" * 70)

    result = (
        DynamicScreen("Liquidity Tiers")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.LIQUIDITY + FieldSets.PRICE + FieldSets.MARKET_CAP)
        .run()
    )

    # Calculate liquidity metrics
    liquidity_data = []
    for rec in result:
        adv = rec.fields.get("AVG_DAILY_VALUE_TRADED_20D") or 0
        mcap = rec.market_cap or 0
        turnover = rec.fields.get("TURNOVER") or 0

        if adv > 0 and mcap > 0:
            # Liquidity ratio = ADV / Market Cap (higher = more liquid relative to size)
            liq_ratio = adv / mcap * 100
            liquidity_data.append((rec, adv, mcap, liq_ratio))

    # Tier by ADV
    tier1 = [(r, adv, mcap, lr) for r, adv, mcap, lr in liquidity_data if adv > 50_000_000]  # >$50M ADV
    tier2 = [(r, adv, mcap, lr) for r, adv, mcap, lr in liquidity_data if 10_000_000 < adv <= 50_000_000]
    tier3 = [(r, adv, mcap, lr) for r, adv, mcap, lr in liquidity_data if adv <= 10_000_000]

    print(f"\nTier 1 - High Liquidity (ADV > $50M): {len(tier1)} securities")
    for rec, adv, mcap, lr in sorted(tier1, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: ADV=${adv/1e6:.0f}M, MCap=${mcap/1e9:.1f}B, Liq%={lr:.3f}%")

    print(f"\nTier 2 - Medium Liquidity ($10M-$50M ADV): {len(tier2)} securities")
    for rec, adv, mcap, lr in sorted(tier2, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: ADV=${adv/1e6:.0f}M, MCap=${mcap/1e9:.1f}B")

    print(f"\nTier 3 - Low Liquidity (ADV < $10M): {len(tier3)} securities")
    for rec, adv, mcap, lr in sorted(tier3, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {rec.ticker}: ADV=${adv/1e6:.1f}M, MCap=${mcap/1e9:.2f}B")

    return {"tier1": tier1, "tier2": tier2, "tier3": tier3}


# =============================================================================
# PATTERN 8: MULTI-SIGNAL COMPOSITE
# =============================================================================

def explore_multi_signal_composite():
    """Combine multiple signals into a composite score."""
    print("\n" + "=" * 70)
    print("PATTERN: Multi-Signal Composite")
    print("=" * 70)

    result = (
        DynamicScreen("Multi-Signal")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.SCREENING_FULL)
        .run()
    )

    # Score each signal component
    scored = []
    for rec in result:
        signals = {}

        # 1. Momentum signal (-1 to +1)
        chg = rec.change_pct or 0
        signals["momentum"] = max(-1, min(1, chg / 3))  # Normalize to [-1, 1]

        # 2. RVOL signal (0 to 1)
        rvol = rec.rvol or 0
        signals["rvol"] = min(1, rvol / 3)  # Cap at 3x

        # 3. RSI signal (-1 to +1, oversold = positive)
        rsi = rec.rsi or 50
        signals["rsi"] = (50 - rsi) / 50  # Oversold = positive

        # 4. Sentiment signal (-1 to +1)
        sent = rec.sentiment or 0
        signals["sentiment"] = max(-1, min(1, sent * 10))  # Scale up

        # 5. Analyst signal (-1 to +1)
        upside = rec.upside or 0
        signals["analyst"] = max(-1, min(1, upside / 20))  # 20% upside = +1

        # Composite score with weights
        composite = (
            signals["momentum"] * 0.25 +
            signals["rvol"] * 0.20 +
            signals["rsi"] * 0.15 +
            signals["sentiment"] * 0.20 +
            signals["analyst"] * 0.20
        )

        scored.append((rec, composite, signals))

    # Sort by composite score
    scored.sort(key=lambda x: x[1], reverse=True)

    print("\nTop 10 - Bullish Composite:")
    for rec, score, signals in scored[:10]:
        print(f"  {rec.ticker}: Score={score:+.2f} "
              f"[Mom={signals['momentum']:+.2f}, RVOL={signals['rvol']:.2f}, "
              f"RSI={signals['rsi']:+.2f}, Sent={signals['sentiment']:+.2f}]")

    print("\nBottom 5 - Bearish Composite:")
    for rec, score, signals in scored[-5:]:
        print(f"  {rec.ticker}: Score={score:+.2f} "
              f"[Mom={signals['momentum']:+.2f}, RVOL={signals['rvol']:.2f}, "
              f"RSI={signals['rsi']:+.2f}, Sent={signals['sentiment']:+.2f}]")

    return scored


# =============================================================================
# PATTERN 9: BID-ASK SPREAD ANALYSIS
# =============================================================================

def explore_bid_ask_analysis():
    """Analyze bid-ask spreads for market quality."""
    print("\n" + "=" * 70)
    print("PATTERN: Bid-Ask Spread Analysis")
    print("=" * 70)

    result = (
        DynamicScreen("Bid-Ask")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.QUOTE + FieldSets.PRICE + FieldSets.LIQUIDITY)
        .run()
    )

    spread_data = []
    for rec in result:
        bid = rec.fields.get("PX_BID") or 0
        ask = rec.fields.get("PX_ASK") or 0
        bid_size = rec.fields.get("BID_SIZE") or 0
        ask_size = rec.fields.get("ASK_SIZE") or 0
        mid = (bid + ask) / 2 if bid and ask else 0

        if mid > 0:
            spread_pct = (ask - bid) / mid * 100
            # Quoted depth
            depth = (bid_size * bid + ask_size * ask)

            spread_data.append((rec, spread_pct, bid_size, ask_size, depth))

    # Sort by spread
    spread_data.sort(key=lambda x: x[1])

    print(f"\nTightest Spreads (Best Execution):")
    for rec, spread, bs, ask_s, depth in spread_data[:5]:
        print(f"  {rec.ticker}: Spread={spread:.3f}%, BidSize={bs:,}, AskSize={ask_s:,}")

    print(f"\nWidest Spreads (Poor Execution):")
    for rec, spread, bs, ask_s, depth in spread_data[-5:]:
        print(f"  {rec.ticker}: Spread={spread:.3f}%, BidSize={bs:,}, AskSize={ask_s:,}")

    return spread_data


# =============================================================================
# PATTERN 10: PRICE LOCATION ANALYSIS
# =============================================================================

def explore_price_location():
    """Analyze where price is within its daily range."""
    print("\n" + "=" * 70)
    print("PATTERN: Price Location Analysis")
    print("=" * 70)

    result = (
        DynamicScreen("Price Location")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields([
            "PX_LAST", "PX_OPEN", "PX_HIGH", "PX_LOW",
            "CHG_PCT_1D", "VOLUME", "VOLUME_AVG_20D"
        ])
        .run()
    )

    # Analyze price location
    closing_high = []   # Price near high of day
    closing_low = []    # Price near low of day
    reversal_up = []    # Opened low, closed high
    reversal_down = []  # Opened high, closed low

    for rec in result:
        px = rec.price or 0
        px_open = rec.fields.get("PX_OPEN") or 0
        px_high = rec.fields.get("PX_HIGH") or 0
        px_low = rec.fields.get("PX_LOW") or 0

        if px_high == px_low or px_high == 0:
            continue

        # Location within range (0 = low, 1 = high)
        location = (px - px_low) / (px_high - px_low)
        open_location = (px_open - px_low) / (px_high - px_low)

        if location > 0.9:  # Near high
            closing_high.append((rec, location, rec.change_pct or 0))
        elif location < 0.1:  # Near low
            closing_low.append((rec, location, rec.change_pct or 0))

        # Reversal patterns
        if open_location < 0.3 and location > 0.7:  # Bullish reversal
            reversal_up.append((rec, open_location, location))
        elif open_location > 0.7 and location < 0.3:  # Bearish reversal
            reversal_down.append((rec, open_location, location))

    print(f"\nClosing Near High ({len(closing_high)}):")
    for rec, loc, chg in sorted(closing_high, key=lambda x: x[2], reverse=True)[:5]:
        print(f"  {rec.ticker}: Location={loc:.0%} of range, Chg={chg:+.1f}%")

    print(f"\nClosing Near Low ({len(closing_low)}):")
    for rec, loc, chg in sorted(closing_low, key=lambda x: x[2])[:5]:
        print(f"  {rec.ticker}: Location={loc:.0%} of range, Chg={chg:+.1f}%")

    print(f"\nBullish Reversals - Opened Low, Closed High ({len(reversal_up)}):")
    for rec, open_loc, close_loc in reversal_up[:5]:
        print(f"  {rec.ticker}: Open@{open_loc:.0%} -> Close@{close_loc:.0%}, Chg={rec.change_pct or 0:+.1f}%")

    print(f"\nBearish Reversals - Opened High, Closed Low ({len(reversal_down)}):")
    for rec, open_loc, close_loc in reversal_down[:5]:
        print(f"  {rec.ticker}: Open@{open_loc:.0%} -> Close@{close_loc:.0%}, Chg={rec.change_pct or 0:+.1f}%")

    return {"closing_high": closing_high, "closing_low": closing_low,
            "reversal_up": reversal_up, "reversal_down": reversal_down}


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print(" EXPLORING ADVANCED SCREENING PATTERNS")
    print("=" * 70)

    explore_momentum_persistence()
    explore_volume_trends()
    explore_gap_analysis()
    explore_cross_sectional_ranking()
    explore_volatility_regimes()
    explore_sector_relative()
    explore_liquidity_tiering()
    explore_multi_signal_composite()
    explore_bid_ask_analysis()
    explore_price_location()

    print("\n" + "=" * 70)
    print(" EXPLORATION COMPLETE")
    print("=" * 70)

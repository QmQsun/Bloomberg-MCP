"""Configuration for morning note tools.

Security universes, field mappings, and constants for morning note generation.
All securities and fields validated against Bloomberg API on 2025-12-17.
"""

from typing import Dict, List, NamedTuple


# =============================================================================
# SECURITY UNIVERSES
# =============================================================================

class SecurityDef(NamedTuple):
    """Security definition with metadata."""
    ticker: str
    name: str
    category: str = ""


# US Indexes
US_INDEXES: Dict[str, SecurityDef] = {
    "spx": SecurityDef("SPX Index", "S&P 500"),
    "dow": SecurityDef("INDU Index", "Dow Jones"),
    "nasdaq": SecurityDef("CCMP Index", "Nasdaq Composite"),
    "russell": SecurityDef("RTY Index", "Russell 2000"),
    "spw": SecurityDef("SPW Index", "S&P 500 Equal Weight"),
}

# Macro Instruments
MACRO_FX: Dict[str, SecurityDef] = {
    "dxy": SecurityDef("DXY Curncy", "Dollar Index"),
    "usdjpy": SecurityDef("USDJPY Curncy", "USD/JPY"),
    "eurjpy": SecurityDef("EURJPY Curncy", "EUR/JPY"),
}

MACRO_RATES: Dict[str, SecurityDef] = {
    "us_10y": SecurityDef("USGG10YR Index", "US 10Y Yield"),
    "us_2y": SecurityDef("USGG2YR Index", "US 2Y Yield"),
    "jp_10y": SecurityDef("JGBS10 Index", "Japan 10Y Yield"),
}

MACRO_COMMODITIES: Dict[str, SecurityDef] = {
    "wti": SecurityDef("CL1 Comdty", "WTI Crude"),
    "brent": SecurityDef("CO1 Comdty", "Brent Crude"),
    "gold": SecurityDef("GC1 Comdty", "Gold"),
}

# S&P Sector ETFs (GICS)
SECTOR_ETFS: List[SecurityDef] = [
    SecurityDef("XLK US Equity", "Technology", "tech"),
    SecurityDef("XLF US Equity", "Financials", "financials"),
    SecurityDef("XLE US Equity", "Energy", "energy"),
    SecurityDef("XLV US Equity", "Healthcare", "healthcare"),
    SecurityDef("XLP US Equity", "Consumer Staples", "staples"),
    SecurityDef("XLI US Equity", "Industrials", "industrials"),
    SecurityDef("XLB US Equity", "Materials", "materials"),
    SecurityDef("XLRE US Equity", "Real Estate", "real_estate"),
    SecurityDef("XLU US Equity", "Utilities", "utilities"),
    SecurityDef("XLC US Equity", "Communication Services", "comm_services"),
    SecurityDef("XLY US Equity", "Consumer Discretionary", "discretionary"),
]

# Industry/Thematic ETFs grouped by theme
INDUSTRY_ETFS: Dict[str, List[SecurityDef]] = {
    "precious_metals": [
        SecurityDef("GDX US Equity", "Gold Miners", "precious_metals"),
        SecurityDef("SIL US Equity", "Silver Miners", "precious_metals"),
    ],
    "base_metals": [
        SecurityDef("COPX US Equity", "Copper Miners", "base_metals"),
        SecurityDef("SLX US Equity", "Steel", "base_metals"),
    ],
    "financials": [
        SecurityDef("KRE US Equity", "Regional Banks", "financials"),
    ],
    "real_estate": [
        SecurityDef("IYR US Equity", "US Real Estate", "real_estate"),
    ],
    "semiconductors": [
        SecurityDef("SMH US Equity", "VanEck Semiconductors", "semiconductors"),
        SecurityDef("SOXX US Equity", "iShares Semiconductors", "semiconductors"),
    ],
    "software": [
        SecurityDef("IGV US Equity", "Software", "software"),
    ],
    "innovation": [
        SecurityDef("ARKW US Equity", "ARK Next Gen Internet", "innovation"),
    ],
    "robotics": [
        SecurityDef("BOTZ US Equity", "Robotics & AI", "robotics"),
    ],
    "energy": [
        SecurityDef("XOP US Equity", "Oil & Gas E&P", "energy"),
    ],
}

# Japan Proxies
JAPAN_PROXIES: Dict[str, SecurityDef] = {
    "nikkei_cash": SecurityDef("NKY Index", "Nikkei 225"),
    "nikkei_futures": SecurityDef("NK1 Index", "Nikkei Futures"),
    "topix": SecurityDef("TPX Index", "TOPIX"),
    "ewj": SecurityDef("EWJ US Equity", "iShares MSCI Japan"),
}

# =============================================================================
# EQS SCREEN CONFIGURATION
# =============================================================================

class ScreenConfig(NamedTuple):
    """EQS screen configuration."""
    name: str
    screen_type: str  # "PRIVATE" or "GLOBAL"
    description: str


# Dynamic ADR screen - fetches liquid Japan ADRs
JAPAN_ADR_SCREEN = ScreenConfig(
    name="Japan_Liquid_ADRs",
    screen_type="PRIVATE",
    description="Japan ADRs with >$10M avg daily value traded",
)

# Sector mapping from GICS to our categories
GICS_TO_SECTOR_MAP: Dict[str, str] = {
    "Financials": "financials",
    "Information Technology": "semiconductors",  # Most JP IT ADRs are semis
    "Consumer Discretionary": "autos",  # Toyota, Honda, Sony
    "Communication Services": "tech",  # SoftBank, Nintendo
    "Industrials": "industrials",
    "Health Care": "healthcare",
    "Materials": "materials",
}

# Sub-industry overrides for more precise categorization
GICS_SUBIND_TO_SECTOR_MAP: Dict[str, str] = {
    "Diversified Banks": "banks",
    "Investment Banking & Brokerage": "banks",
    "Property & Casualty Insurance": "insurance",
    "Automobile Manufacturers": "autos",
    "Consumer Electronics": "tech",
    "Semiconductor Materials & Equipment": "semiconductors",
    "Wireless Telecommunication Services": "tech",
    "Interactive Home Entertainment": "tech",
    "Industrial Machinery & Supplies & Components": "industrials",
    "Industrial Conglomerates": "industrials",
    "Human Resource & Employment Services": "industrials",
    "Pharmaceuticals": "healthcare",
    "Specialty Chemicals": "materials",
}


# =============================================================================
# STATIC ADR LIST (Fallback if screen unavailable)
# =============================================================================

# Japan ADRs grouped by sector
class ADRDef(NamedTuple):
    """ADR definition with underlying mapping."""
    adr_ticker: str
    jp_code: str
    name: str
    sector: str


JAPAN_ADRS: Dict[str, List[ADRDef]] = {
    "banks": [
        ADRDef("MUFG US Equity", "8306 JP Equity", "Mitsubishi UFJ Financial", "banks"),
        ADRDef("SMFG US Equity", "8316 JP Equity", "Sumitomo Mitsui Financial", "banks"),
        ADRDef("MFG US Equity", "8411 JP Equity", "Mizuho Financial", "banks"),
        ADRDef("NMR US Equity", "8604 JP Equity", "Nomura Holdings", "banks"),
    ],
    "autos": [
        ADRDef("TM US Equity", "7203 JP Equity", "Toyota Motor", "autos"),
        ADRDef("HMC US Equity", "7267 JP Equity", "Honda Motor", "autos"),
    ],
    "tech": [
        ADRDef("SFTBY US Equity", "9984 JP Equity", "SoftBank Group", "tech"),
        ADRDef("SONY US Equity", "6758 JP Equity", "Sony Group", "tech"),
        ADRDef("NTDOY US Equity", "7974 JP Equity", "Nintendo", "tech"),
    ],
    "semiconductors": [
        ADRDef("TOELY US Equity", "8035 JP Equity", "Tokyo Electron", "semiconductors"),
        ADRDef("DSCSY US Equity", "6146 JP Equity", "Disco Corp", "semiconductors"),
        ADRDef("RNECY US Equity", "6723 JP Equity", "Renesas Electronics", "semiconductors"),
    ],
    "telecom": [
        ADRDef("KDDIY US Equity", "9433 JP Equity", "KDDI Corp", "telecom"),
    ],
    "healthcare": [
        ADRDef("CHGCY US Equity", "4519 JP Equity", "Chugai Pharmaceutical", "healthcare"),
        ADRDef("TRUMY US Equity", "4543 JP Equity", "Terumo Corp", "healthcare"),
    ],
    "insurance": [
        ADRDef("TKOMY US Equity", "8766 JP Equity", "Tokio Marine", "insurance"),
    ],
    "electronics": [
        ADRDef("TTDKY US Equity", "6762 JP Equity", "TDK Corp", "electronics"),
    ],
}

# Japan Equity Watchlist (for Opening Bell section)
class JPEquityDef(NamedTuple):
    """Japan equity definition."""
    ticker: str
    code: str
    name: str
    theme: str


JAPAN_WATCHLIST: Dict[str, List[JPEquityDef]] = {
    "banks": [
        JPEquityDef("8306 JP Equity", "8306", "MUFG", "banks"),
        JPEquityDef("8411 JP Equity", "8411", "Mizuho", "banks"),
        JPEquityDef("8604 JP Equity", "8604", "Nomura", "banks"),
    ],
    "autos": [
        JPEquityDef("7203 JP Equity", "7203", "Toyota", "autos"),
        JPEquityDef("7267 JP Equity", "7267", "Honda", "autos"),
        JPEquityDef("7261 JP Equity", "7261", "Mazda", "autos"),
    ],
    "semiconductors": [
        JPEquityDef("8035 JP Equity", "8035", "Tokyo Electron", "semiconductors"),
        JPEquityDef("6857 JP Equity", "6857", "Advantest", "semiconductors"),
        JPEquityDef("6146 JP Equity", "6146", "Disco", "semiconductors"),
        JPEquityDef("6920 JP Equity", "6920", "Lasertec", "semiconductors"),
    ],
    "tech": [
        JPEquityDef("9984 JP Equity", "9984", "SoftBank", "tech"),
    ],
    "materials": [
        JPEquityDef("5713 JP Equity", "5713", "Sumitomo Metal Mining", "materials"),
        JPEquityDef("5711 JP Equity", "5711", "Mitsubishi Materials", "materials"),
        JPEquityDef("5714 JP Equity", "5714", "Dowa Holdings", "materials"),
    ],
    "energy": [
        JPEquityDef("1605 JP Equity", "1605", "Inpex", "energy"),
    ],
    "robotics": [
        JPEquityDef("6954 JP Equity", "6954", "FANUC", "robotics"),
        JPEquityDef("6506 JP Equity", "6506", "Yaskawa", "robotics"),
    ],
    "mask_supply_chain": [
        JPEquityDef("7912 JP Equity", "7912", "DNP", "mask_supply_chain"),
        JPEquityDef("7741 JP Equity", "7741", "HOYA", "mask_supply_chain"),
    ],
    "healthcare": [
        JPEquityDef("4519 JP Equity", "4519", "Chugai", "healthcare"),
        JPEquityDef("4543 JP Equity", "4543", "Terumo", "healthcare"),
    ],
}


# =============================================================================
# FIELD MAPPINGS
# =============================================================================

# Core price/performance fields
PRICE_FIELDS = [
    "PX_LAST",
    "CHG_PCT_1D",
    "PX_OPEN",
    "PX_HIGH",
    "PX_LOW",
]

# Volume fields for RVOL calculation
VOLUME_FIELDS = [
    "VOLUME",
    "VOLUME_AVG_20D",
]

# ADR-specific fields (for reference data calls - fallback only)
ADR_FIELDS = [
    "PX_LAST",
    "CHG_PCT_1D",
    "PX_OPEN",
    "PX_CLOSE_1D",
    "VOLUME",
    "VOLUME_AVG_20D",
    "ADR_UNDL_TICKER",
    "NAME",
]

# EQS Screen output fields (Japan_Liquid_ADRs)
# These are the columns returned by the screen - not Bloomberg mnemonics
ADR_SCREEN_FIELDS = [
    "security",                         # Full Bloomberg ticker (e.g., "TOELY US")
    "Ticker",                           # Short ticker
    "Short Name",                       # Company short name
    "Und Tkr",                          # Underlying JP ticker (e.g., "8035 JP")
    "GICS Sector",                      # GICS Sector Name
    "GICS SubInd Name",                 # GICS Sub-Industry Name
    "Average Volume:D-20",              # 20-day avg volume (shares)
    "Avg D Val Traded 20D:D-20",        # 20-day avg daily value traded (USD)
    "Market Cap",                       # Market capitalization
    "Volat:D-30",                       # 30-day volatility
    "Overridable Raw Beta",             # Raw beta
    "ADR Spons Typ",                    # ADR sponsor type
    "Shares/ADR",                       # Shares per ADR
    "ADR Trdg Lvl",                     # ADR trading level
    "Converted Underlying Price Close", # Underlying price converted to ADR terms
    "Converted ADR Price Close",        # ADR close price
]

# Japan equity fields
JP_EQUITY_FIELDS = [
    "PX_LAST",
    "CHG_PCT_1D",
    "NAME",
    "GICS_SECTOR_NAME",
]

# Index fields (no volume for some)
INDEX_FIELDS = [
    "PX_LAST",
    "CHG_PCT_1D",
    "PX_OPEN",
    "PX_HIGH",
    "PX_LOW",
]

# Macro fields (FX, rates, commodities)
MACRO_FIELDS = [
    "PX_LAST",
    "CHG_PCT_1D",
    "PX_OPEN",
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_sector_tickers() -> List[str]:
    """Get all sector ETF tickers."""
    return [s.ticker for s in SECTOR_ETFS]


def get_all_industry_tickers() -> List[str]:
    """Get all industry ETF tickers across themes."""
    tickers = []
    for theme_etfs in INDUSTRY_ETFS.values():
        tickers.extend([e.ticker for e in theme_etfs])
    return tickers


def get_all_adr_tickers() -> List[str]:
    """Get all Japan ADR tickers."""
    tickers = []
    for sector_adrs in JAPAN_ADRS.values():
        tickers.extend([a.adr_ticker for a in sector_adrs])
    return tickers


def get_all_jp_watchlist_tickers() -> List[str]:
    """Get all Japan equity watchlist tickers."""
    tickers = []
    for theme_equities in JAPAN_WATCHLIST.values():
        tickers.extend([e.ticker for e in theme_equities])
    return tickers


def get_adr_by_ticker(ticker: str) -> ADRDef | None:
    """Look up ADR definition by ticker."""
    for sector_adrs in JAPAN_ADRS.values():
        for adr in sector_adrs:
            if adr.adr_ticker == ticker:
                return adr
    return None

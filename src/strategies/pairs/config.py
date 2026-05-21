"""Hard-coded pair definitions and default strategy parameters."""

PAIRS = [
    # Financials — all validated OOS (Sharpe > 1.0)
    {"ticker_a": "GS",   "ticker_b": "BAC",   "sector": "Financials"},
    {"ticker_a": "GS",   "ticker_b": "C",     "sector": "Financials"},
    {"ticker_a": "JPM",  "ticker_b": "BAC",   "sector": "Financials"},
    {"ticker_a": "GS",   "ticker_b": "MS",    "sector": "Financials"},
    # Consumer Staples — validated OOS
    {"ticker_a": "KO",   "ticker_b": "PEP",   "sector": "Consumer Staples"},
    # Energy — validated OOS
    {"ticker_a": "SLB",  "ticker_b": "HAL",   "sector": "Energy"},
    {"ticker_a": "PSX",  "ticker_b": "VLO",   "sector": "Energy"},
    {"ticker_a": "XOM",  "ticker_b": "CVX",   "sector": "Energy"},
    # Other
    {"ticker_a": "MSFT", "ticker_b": "GOOGL", "sector": "Technology"},
    {"ticker_a": "DAL",  "ticker_b": "UAL",   "sector": "Airlines"},
    {"ticker_a": "CVS",  "ticker_b": "MCK",   "sector": "Pharmacy"},
]

DEFAULT_PARAMS = {
    "period": "2y",       # lookback window for data fetch
    "z_entry": 2.0,       # enter when |z-score| exceeds this
    "z_exit": 0.5,        # exit when |z-score| falls below this
    "z_stop": 3.0,        # stop-loss: close if |z-score| exceeds this
    "rolling_window": 60, # days for rolling z-score mean/std
}

SCAN_UNIVERSES = {
    # ── Small focused universes (fast, sector-specific) ───────────────────────
    "financials": ["GS", "MS", "JPM", "BAC", "C", "WFC", "BLK", "SCHW"],
    "energy":     ["XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO"],
    "airlines":   ["DAL", "UAL", "AAL", "LUV", "ALK"],
    "pharmacy":   ["CVS", "MCK", "CAH", "CI", "HUM"],
    "tech":       ["MSFT", "GOOGL", "META", "AAPL", "AMZN", "NVDA"],
    "staples":    ["KO", "PEP", "PG", "CL", "KMB", "GIS"],

    # ── Large cross-sector universe (~95 liquid large-caps) ───────────────────
    # Produces ~4,400 candidate pairs; correlation filter trims this to ~50-200
    # before ADF testing. Expect ~30-90 seconds on a 2y period.
    "large_cap": [
        # Financials — banks, brokers, exchanges, insurance
        "GS", "MS", "JPM", "BAC", "C", "WFC", "BLK", "SCHW",
        "AXP", "COF", "USB", "PNC", "SPGI", "MCO", "ICE", "CME",
        # Energy — majors, refiners, E&P, services
        "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO", "MPC",
        "OXY", "HAL", "BKR", "DVN",
        # Technology — mega-cap, semis, software, hardware
        "MSFT", "GOOGL", "META", "AAPL", "AMZN", "NVDA", "AMD",
        "INTC", "QCOM", "TXN", "AVGO", "MU", "AMAT", "CRM", "ORCL", "CSCO",
        # Consumer Staples
        "KO", "PEP", "PG", "CL", "KMB", "GIS", "CAG",
        "HSY", "MDLZ", "MO", "PM",
        # Healthcare — pharma, biotech, managed care
        "JNJ", "PFE", "MRK", "ABBV", "LLY", "BMY", "AMGN", "GILD",
        "CVS", "MCK", "UNH", "HUM",
        # Industrials — defense, aerospace, diversified
        "BA", "LMT", "RTX", "NOC", "GD", "HON", "GE", "MMM", "CAT", "DE",
        # Consumer Discretionary — retail, restaurants
        "WMT", "TGT", "COST", "HD", "LOW", "MCD", "NKE",
        # Airlines
        "DAL", "UAL", "AAL", "LUV", "ALK",
        # Materials — metals, mining, steel
        "NEM", "FCX", "NUE", "STLD", "AA",
    ],

    # ── Broad S&P 500 universe (~230 liquid names across all sectors) ──────────
    # Produces ~26,000 candidate pairs; correlation filter (default 0.80) trims
    # to ~300-800 before ADF testing. Expect 3-8 minutes on a 3y period.
    # Use --data-provider alpaca for faster, more reliable bulk fetching.
    "sp500": [
        # Financials — banks, brokers, custodians, exchanges, insurance
        "GS", "MS", "JPM", "BAC", "C", "WFC", "BLK", "SCHW",
        "AXP", "COF", "USB", "PNC", "TFC", "FITB", "HBAN", "KEY", "RF",
        "SPGI", "MCO", "ICE", "CME", "BK", "STT",
        "TRV", "AIG", "MET", "PRU", "ALL", "CB", "MMC", "AON",
        # Energy — majors, refiners, E&P, midstream, services
        "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO", "MPC",
        "OXY", "HAL", "BKR", "DVN", "HES", "MRO", "APA", "CTRA",
        "WMB", "OKE", "TRGP", "KMI",
        # Technology — mega-cap, semis, software, hardware, storage
        "MSFT", "AAPL", "NVDA", "GOOGL", "META", "AMZN",
        "AMD", "INTC", "QCOM", "TXN", "AVGO", "MU", "AMAT", "LRCX", "KLAC",
        "CRM", "ORCL", "CSCO", "IBM", "ACN", "INTU", "NOW", "WDAY", "ADSK",
        "CDNS", "SNPS", "ANSS", "FTNT", "PANW",
        "HPQ", "HPE", "WDC", "STX",
        # Consumer Staples — beverages, food, tobacco, HPC
        "KO", "PEP", "PG", "CL", "KMB", "GIS", "CAG",
        "HSY", "MDLZ", "MO", "PM", "STZ", "TAP",
        "CPB", "K", "SJM", "HRL", "TSN", "MKC",
        # Healthcare — pharma, biotech, managed care, devices, distributors
        "JNJ", "PFE", "MRK", "ABBV", "LLY", "BMY", "AMGN", "GILD",
        "REGN", "VRTX", "BIIB",
        "UNH", "HUM", "CI", "MOH", "CNC",
        "CVS", "MCK", "ABC",
        "MDT", "BSX", "EW", "ISRG", "SYK", "BDX", "BAX", "ZBH",
        "TMO", "DHR", "A", "IQV",
        # Industrials — defense, aero, machinery, transport, waste
        "BA", "LMT", "RTX", "NOC", "GD",
        "HON", "GE", "MMM", "EMR", "ETN", "PH", "ROK", "IR", "ITW", "SWK",
        "CAT", "DE",
        "UPS", "FDX", "CSX", "UNP", "NSC",
        "WM", "RSG", "CTAS",
        # Consumer Discretionary — retail, restaurants, autos, travel
        "WMT", "COST", "TGT", "HD", "LOW",
        "MCD", "SBUX", "YUM", "DRI", "CMG",
        "NKE", "TJX", "ROST",
        "BKNG", "EXPE",
        "GM", "F", "TSLA", "APTV",
        "MGM", "LVS", "HLT", "MAR",
        # Airlines
        "DAL", "UAL", "AAL", "LUV", "ALK",
        # Communication Services — streaming, media, telecom
        "NFLX", "DIS", "CMCSA", "CHTR",
        "VZ", "T", "TMUS",
        # Materials — chemicals, metals, mining, steel
        "LIN", "APD", "DD", "DOW", "LYB", "EMN",
        "SHW", "PPG",
        "NEM", "FCX", "AA", "NUE", "STLD", "CLF",
        # Utilities
        "NEE", "DUK", "SO", "AEP", "EXC", "SRE", "PEG", "WEC",
        # REITs
        "AMT", "PLD", "CCI", "EQIX", "PSA", "DLR", "O", "SPG",
    ],
}

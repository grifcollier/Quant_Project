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
}

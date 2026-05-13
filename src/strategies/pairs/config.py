"""Hard-coded pair definitions and default strategy parameters."""

PAIRS = [
    {"ticker_a": "KO",   "ticker_b": "PEP",   "sector": "Consumer Staples"},
    {"ticker_a": "JPM",  "ticker_b": "BAC",   "sector": "Financials"},
    {"ticker_a": "XOM",  "ticker_b": "CVX",   "sector": "Energy"},
    {"ticker_a": "MSFT", "ticker_b": "GOOGL", "sector": "Technology"},
    {"ticker_a": "GS",   "ticker_b": "MS",    "sector": "Financials"},
    {"ticker_a": "DAL",  "ticker_b": "UAL",   "sector": "Airlines"},
    {"ticker_a": "CVS",  "ticker_b": "WBA",   "sector": "Pharmacy"},
]

DEFAULT_PARAMS = {
    "period": "2y",       # lookback window for data fetch
    "z_entry": 2.0,       # enter when |z-score| exceeds this
    "z_exit": 0.5,        # exit when |z-score| falls below this
    "z_stop": 3.0,        # stop-loss: close if |z-score| exceeds this
    "rolling_window": 60, # days for rolling z-score mean/std
}

SCAN_UNIVERSES = {
    "financials": ["GS", "MS", "JPM", "BAC", "C", "WFC", "BLK", "SCHW"],
    "energy":     ["XOM", "CVX", "COP", "SLB", "EOG", "PSX", "VLO"],
    "airlines":   ["DAL", "UAL", "AAL", "LUV", "ALK"],
    "pharmacy":   ["CVS", "WBA", "MCK", "CAH"],
    "tech":       ["MSFT", "GOOGL", "META", "AAPL", "AMZN", "NVDA"],
    "staples":    ["KO", "PEP", "PG", "CL", "KMB", "GIS"],
}

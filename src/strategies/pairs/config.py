"""Hard-coded pair definitions and default strategy parameters."""

PAIRS = [
    {"ticker_a": "KO",   "ticker_b": "PEP",   "sector": "Consumer Staples"},
    {"ticker_a": "JPM",  "ticker_b": "BAC",   "sector": "Financials"},
    {"ticker_a": "XOM",  "ticker_b": "CVX",   "sector": "Energy"},
    {"ticker_a": "MSFT", "ticker_b": "GOOGL", "sector": "Technology"},
]

DEFAULT_PARAMS = {
    "period": "2y",       # lookback window for data fetch
    "z_entry": 2.0,       # enter when |z-score| exceeds this
    "z_exit": 0.5,        # exit when |z-score| falls below this
    "z_stop": 3.0,        # stop-loss: close if |z-score| exceeds this
    "rolling_window": 60, # days for rolling z-score mean/std
}

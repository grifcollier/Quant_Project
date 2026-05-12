"""Price data fetching with simple CSV caching."""

from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parents[2] / "data" / "cache"
_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def fetch_ohlcv(
    ticker: str,
    period: str,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch full OHLCV data for a single ticker.
    Returns a DataFrame with columns ['open','high','low','close','volume'], indexed by date.
    Cache files that predate the OHLCV upgrade (single 'close' column) are automatically refreshed.
    """
    cache_path = CACHE_DIR / f"{ticker}_{period}_{interval}.csv"

    if use_cache and cache_path.exists():
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if all(c in df.columns for c in _OHLCV_COLS):
            return df[_OHLCV_COLS]
        # Old single-column cache — fall through to re-fetch

    raw = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if raw.empty:
        raise ValueError(f"No data returned for {ticker}")

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = _OHLCV_COLS
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path)

    return df


def fetch_price(
    ticker: str,
    period: str,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.Series:
    """
    Fetch adjusted closing prices for a single ticker.
    Returns a pd.Series indexed by date.
    """
    s = fetch_ohlcv(ticker, period, interval, use_cache)["close"]
    s.name = ticker
    return s


def fetch_pair(
    ticker_a: str,
    ticker_b: str,
    period: str = "2y",
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch and align closing prices for two tickers.
    Returns a DataFrame with columns ['close_a', 'close_b'], NaN rows dropped.
    """
    a = fetch_price(ticker_a, period=period, interval=interval, use_cache=use_cache)
    b = fetch_price(ticker_b, period=period, interval=interval, use_cache=use_cache)

    df = pd.DataFrame({"close_a": a, "close_b": b}).dropna()
    df.index.name = "date"
    return df


def fetch_pair_ohlcv(
    ticker_a: str,
    ticker_b: str,
    period: str = "2y",
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch and align full OHLCV for two tickers.
    Returns a DataFrame with columns
    ['open_a','high_a','low_a','close_a','volume_a', 'open_b',...,'volume_b'],
    NaN rows dropped.
    """
    a = fetch_ohlcv(ticker_a, period=period, interval=interval, use_cache=use_cache)
    b = fetch_ohlcv(ticker_b, period=period, interval=interval, use_cache=use_cache)

    a = a.add_suffix("_a")
    b = b.add_suffix("_b")

    df = pd.concat([a, b], axis=1).dropna()
    df.index.name = "date"
    return df

"""Price data fetching with simple CSV caching."""

from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parents[2] / "data" / "cache"
_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def _to_yf(ticker: str) -> str:
    """
    Convert a share-class ticker to yfinance format.

    yfinance uses a dash for share classes (BRK-B) whereas SEC/Alpaca and many
    data sources use a dot (BRK.B). The original ticker is still used as the
    cache key and Series name; only the download symbol is converted.
    """
    return ticker.replace(".", "-")


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

    raw = yf.download(_to_yf(ticker), period=period, interval=interval,
                      auto_adjust=True, progress=False)
    if raw.empty:
        raise ValueError(f"No data returned for {ticker}")

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = _OHLCV_COLS
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
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


def fetch_prices_bulk(
    tickers: list,
    period: str,
    interval: str = "1d",
    provider: str = "yfinance",
) -> dict:
    """
    Fetch closing prices for many tickers efficiently.

    provider="yfinance" (default): serves from per-ticker CSV cache, batch-downloads missing.
    provider="alpaca": uses Alpaca Market Data API (requires ALPACA_API_KEY / ALPACA_SECRET_KEY).

    Returns {ticker: pd.Series of closing prices}. Tickers that fail are omitted.
    """
    if provider == "alpaca":
        from src.data.alpaca_fetcher import fetch_prices_bulk_alpaca
        return fetch_prices_bulk_alpaca(tickers, period=period, interval=interval)
    prices = {}
    to_download = []

    for ticker in tickers:
        cache_path = CACHE_DIR / f"{ticker}_{period}_{interval}.csv"
        if cache_path.exists():
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            if all(c in df.columns for c in _OHLCV_COLS):
                s = df["close"]
                s.name = ticker
                prices[ticker] = s
                continue
        to_download.append(ticker)

    if not to_download:
        return prices

    # Map yfinance download symbol (BRK-B) back to the original ticker (BRK.B)
    yf_map = {_to_yf(t): t for t in to_download}

    raw = yf.download(
        list(yf_map), period=period, interval=interval,
        auto_adjust=True, progress=False,
    )
    if raw.empty:
        return prices

    # yf.download returns flat columns for a single ticker, MultiIndex for many
    if len(yf_map) == 1:
        ticker = to_download[0]
        if "Close" in raw.columns:
            s = raw["Close"].dropna()
            s.name = ticker
            if len(s) >= 10:
                prices[ticker] = s
    else:
        level0 = raw.columns.get_level_values(0)
        if "Close" not in level0:
            return prices
        close_df = raw["Close"]
        for yf_sym, ticker in yf_map.items():
            if yf_sym not in close_df.columns:
                continue
            s = close_df[yf_sym].dropna()
            if len(s) >= 10:
                s.name = ticker
                prices[ticker] = s

    return prices


def fetch_ohlcv_bulk(
    tickers: list,
    period: str,
    interval: str = "1d",
    provider: str = "yfinance",
) -> dict:
    """
    Fetch full OHLCV DataFrames for many tickers.

    Returns {ticker: pd.DataFrame with columns [open,high,low,close,volume]}.
    Separate from fetch_prices_bulk() to keep existing callers unchanged.
    """
    if provider == "alpaca":
        from src.data.alpaca_fetcher import fetch_ohlcv_bulk_alpaca
        return fetch_ohlcv_bulk_alpaca(tickers, period=period, interval=interval)

    result = {}
    for ticker in tickers:
        try:
            result[ticker] = fetch_ohlcv(ticker, period=period, interval=interval)
        except Exception:
            pass
    return result


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

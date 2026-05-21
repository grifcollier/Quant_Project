"""Alpaca Market Data API price fetcher (alternative to yfinance)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).parents[2] / "data" / "cache"

_PERIOD_DAYS = {
    "3mo": 92, "6mo": 183, "1y": 365, "2y": 730,
    "3y": 1095, "5y": 1825, "10y": 3650,
}


def _get_client():
    """Return an Alpaca StockHistoricalDataClient, reading keys from env."""
    from alpaca.data.historical import StockHistoricalDataClient

    api_key    = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        raise ValueError(
            "Alpaca API keys not set. Export ALPACA_API_KEY and ALPACA_SECRET_KEY "
            "environment variables before using --data-provider alpaca.\n"
            "Free keys available at https://alpaca.markets/"
        )
    return StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)


def _period_to_dates(period: str) -> tuple:
    """Convert a period string to (start, end) datetime objects."""
    days = _PERIOD_DAYS.get(period)
    if days is None:
        raise ValueError(f"Unsupported period '{period}'. Use one of: {list(_PERIOD_DAYS)}")
    end   = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    return start, end


def fetch_prices_bulk_alpaca(
    tickers: list,
    period: str,
    interval: str = "1d",
) -> dict:
    """
    Fetch daily closing prices from Alpaca Market Data API.

    Returns {ticker: pd.Series of closing prices}, same format as fetch_prices_bulk().
    Caches per ticker to data/cache/{ticker}_{period}_{interval}_alpaca.csv.

    Requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.
    """
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    if interval != "1d":
        raise ValueError(f"Alpaca fetcher only supports interval='1d', got '{interval}'.")

    start, end = _period_to_dates(period)
    prices = {}
    to_download = []

    # Serve from cache where available
    for ticker in tickers:
        cache_path = CACHE_DIR / f"{ticker}_{period}_{interval}_alpaca.csv"
        if cache_path.exists():
            s = pd.read_csv(cache_path, index_col=0, parse_dates=True).squeeze()
            s.name = ticker
            if len(s) >= 10:
                prices[ticker] = s
                continue
        to_download.append(ticker)

    if not to_download:
        return prices

    client = _get_client()
    request = StockBarsRequest(
        symbol_or_symbols=to_download,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        adjustment="all",
    )

    try:
        bars = client.get_stock_bars(request)
    except Exception as exc:
        msg = str(exc)
        if "401" in msg or "Unauthorized" in msg:
            raise PermissionError(
                "Alpaca data API returned 401 Unauthorized.\n"
                "Live account API keys are required for market data — "
                "paper-only keys do not have data API access.\n"
                "Get live keys from: alpaca.markets > Live Trading > API Keys"
            ) from exc
        raise
    bars_df = bars.df

    if bars_df.empty:
        return prices

    # bars_df has MultiIndex (symbol, timestamp) — pivot to (timestamp, symbol)
    bars_df = bars_df.reset_index()
    close_pivot = bars_df.pivot(index="timestamp", columns="symbol", values="close")
    close_pivot.index = pd.to_datetime(close_pivot.index).tz_localize(None).normalize()
    close_pivot.index.name = "date"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for ticker in to_download:
        if ticker not in close_pivot.columns:
            continue
        s = close_pivot[ticker].dropna()
        if len(s) < 10:
            continue
        s.name = ticker
        prices[ticker] = s
        cache_path = CACHE_DIR / f"{ticker}_{period}_{interval}_alpaca.csv"
        s.to_frame("close").to_csv(cache_path)

    return prices


def fetch_ohlcv_bulk_alpaca(
    tickers: list,
    period: str,
    interval: str = "1d",
) -> dict:
    """
    Fetch full OHLCV DataFrames from Alpaca for many tickers.

    Returns {ticker: pd.DataFrame with columns [open,high,low,close,volume]}.
    """
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    if interval != "1d":
        raise ValueError(f"Alpaca fetcher only supports interval='1d', got '{interval}'.")

    start, end = _period_to_dates(period)
    client  = _get_client()
    request = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        adjustment="all",
    )

    try:
        bars = client.get_stock_bars(request)
    except Exception as exc:
        msg = str(exc)
        if "401" in msg or "Unauthorized" in msg:
            raise PermissionError(
                "Alpaca data API returned 401 Unauthorized.\n"
                "Live account API keys are required for market data — "
                "paper-only keys do not have data API access.\n"
                "Get live keys from: alpaca.markets > Live Trading > API Keys"
            ) from exc
        raise

    bars_df = bars.df
    if bars_df.empty:
        return {}

    bars_df = bars_df.reset_index()
    bars_df["timestamp"] = pd.to_datetime(bars_df["timestamp"]).dt.tz_localize(None).dt.normalize()

    result = {}
    for ticker in tickers:
        t_df = bars_df[bars_df["symbol"] == ticker].copy()
        if t_df.empty:
            continue
        t_df = t_df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
        t_df.index.name = "date"
        if len(t_df) >= 10:
            result[ticker] = t_df

    return result

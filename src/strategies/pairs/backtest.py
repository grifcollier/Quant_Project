"""Pairs-specific backtest: position sizing, trade log construction, and results."""

from typing import Union

import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.metrics import compute_metrics


def build_trade_log(
    signals_df: pd.DataFrame,
    df_ohlcv: pd.DataFrame,
    hedge_ratio: Union[float, pd.Series],
    capital_per_leg: float = 10_000.0,
) -> pd.DataFrame:
    """
    Build a completed trade log from signals and OHLCV prices.

    Uses close-to-close fills: enter at the close on the signal bar,
    exit at the close on the exit/stop bar.

    Position sizing is hedge-ratio adjusted and dollar-neutral per leg:
      Long spread:  shares_a = +capital/close_a,  shares_b = -(capital*beta/close_b)
      Short spread: shares_a = -capital/close_a,  shares_b = +(capital*beta/close_b)

    Parameters
    ----------
    signals_df     : Output of generate_signals() — columns ['zscore','signal','position'].
    df_ohlcv       : Output of fetch_pair_ohlcv() — must contain 'close_a' and 'close_b'.
    hedge_ratio    : Beta from compute_hedge_ratio() (float), or a date-indexed
                     Series from compute_rolling_hedge_ratio(). When a Series is
                     passed, the beta at each entry date is used — no look-ahead.
    capital_per_leg: Dollars allocated per leg (total capital = 2x this).

    Returns
    -------
    DataFrame with one row per completed trade.
    """
    rolling_mode = isinstance(hedge_ratio, pd.Series)

    trades = []
    open_trade = None  # dict of current open position

    for date, row in signals_df.iterrows():
        sig = row["signal"]

        if sig in ("long_spread", "short_spread"):
            if open_trade is not None:
                continue  # already in a position — state machine guarantees this won't happen
            close_a = df_ohlcv.loc[date, "close_a"]
            close_b = df_ohlcv.loc[date, "close_b"]
            direction = 1 if sig == "long_spread" else -1
            hr = hedge_ratio.loc[date] if rolling_mode else hedge_ratio
            shares_a = direction * capital_per_leg / close_a
            shares_b = -direction * capital_per_leg * hr / close_b
            open_trade = {
                "entry_date":       date,
                "direction":        direction,
                "entry_price_a":    close_a,
                "entry_price_b":    close_b,
                "shares_a":         shares_a,
                "shares_b":         shares_b,
                "hedge_ratio_used": hr,
            }

        elif sig in ("exit", "stop") and open_trade is not None:
            close_a = df_ohlcv.loc[date, "close_a"]
            close_b = df_ohlcv.loc[date, "close_b"]
            pnl = (
                open_trade["shares_a"] * (close_a - open_trade["entry_price_a"])
                + open_trade["shares_b"] * (close_b - open_trade["entry_price_b"])
            )
            trades.append({
                "entry_date":       open_trade["entry_date"],
                "exit_date":        date,
                "exit_type":        sig,
                "direction":        open_trade["direction"],
                "entry_price_a":    open_trade["entry_price_a"],
                "entry_price_b":    open_trade["entry_price_b"],
                "exit_price_a":     close_a,
                "exit_price_b":     close_b,
                "shares_a":         open_trade["shares_a"],
                "shares_b":         open_trade["shares_b"],
                "hedge_ratio_used": open_trade["hedge_ratio_used"],
                "pnl":              round(pnl, 4),
                "pnl_pct":          round(pnl / (2 * capital_per_leg), 6),
            })
            open_trade = None

    if not trades:
        cols = [
            "entry_date", "exit_date", "exit_type", "direction",
            "entry_price_a", "entry_price_b", "exit_price_a", "exit_price_b",
            "shares_a", "shares_b", "hedge_ratio_used", "pnl", "pnl_pct",
        ]
        return pd.DataFrame(columns=cols)

    return pd.DataFrame(trades)


def run_pairs_backtest(
    ticker_a: str,
    ticker_b: str,
    signals_df: pd.DataFrame,
    df_ohlcv: pd.DataFrame,
    hedge_ratio: Union[float, pd.Series],
    capital_per_leg: float = 10_000.0,
) -> tuple:
    """
    Run the full pairs backtest pipeline.

    Returns
    -------
    (trades, equity_curve, metrics) — three objects for downstream display.
    """
    starting_capital = 2 * capital_per_leg

    trades = build_trade_log(signals_df, df_ohlcv, hedge_ratio, capital_per_leg)
    equity_curve = run_backtest(trades, starting_capital)
    metrics = compute_metrics(equity_curve, trades, starting_capital)

    return trades, equity_curve, metrics

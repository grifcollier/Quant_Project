"""Pairs-specific backtest: position sizing, trade log construction, and results."""

from typing import Union

import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.metrics import compute_metrics
from src.analytics.market_beta import compute_beta_neutral_allocation


def build_trade_log(
    signals_df: pd.DataFrame,
    df_ohlcv: pd.DataFrame,
    hedge_ratio: Union[float, pd.Series],
    capital_per_leg: float = 10_000.0,
    market_beta_a: pd.Series = None,
    market_beta_b: pd.Series = None,
    max_hold_bars: int = None,
    max_loss_pct: float = None,
) -> pd.DataFrame:
    """
    Build a completed trade log from signals and OHLCV prices.

    Uses close-to-close fills: enter at the close on the signal bar,
    exit at the close on the exit/stop bar.

    Position sizing solves for dollar-neutral AND beta-neutral simultaneously:
      V_a = total_capital * β_b / (β_a + β_b)
      V_b = total_capital * β_a / (β_a + β_b)

    When market betas are not provided, falls back to equal dollar splits
    (β_a = β_b = 1), which is equivalent to the original dollar-neutral sizing.

    Parameters
    ----------
    signals_df     : Output of generate_signals() — columns ['zscore','signal','position'].
    df_ohlcv       : Output of fetch_pair_ohlcv() — must contain 'close_a' and 'close_b'.
    hedge_ratio    : Cointegration beta (float or date-indexed Series). Used to
                     record the hedge ratio at entry; signal generation already
                     incorporates it via the spread computation.
    capital_per_leg: Half of total capital (total = 2x this).
    market_beta_a  : Rolling market beta Series for ticker A (vs SPY). Optional.
    market_beta_b  : Rolling market beta Series for ticker B (vs SPY). Optional.

    Returns
    -------
    DataFrame with one row per completed trade.
    """
    rolling_mode = isinstance(hedge_ratio, pd.Series)
    total_capital = 2 * capital_per_leg

    trades = []
    open_trade = None

    for date, row in signals_df.iterrows():
        sig = row["signal"]

        if open_trade is not None:
            close_a = df_ohlcv.loc[date, "close_a"]
            close_b = df_ohlcv.loc[date, "close_b"]
            open_trade["bars_held"] += 1
            unrealized = (
                open_trade["shares_a"] * (close_a - open_trade["entry_price_a"])
                + open_trade["shares_b"] * (close_b - open_trade["entry_price_b"])
            )

            # Forced exits checked before signal exits
            forced = None
            if max_loss_pct is not None and unrealized / total_capital < -max_loss_pct:
                forced = "dollar_stop"
            elif max_hold_bars is not None and open_trade["bars_held"] >= max_hold_bars:
                forced = "time_stop"

            exit_type = forced if forced else (sig if sig in ("exit", "stop") else None)

            if exit_type:
                pnl = unrealized
                trades.append({
                    "entry_date":       open_trade["entry_date"],
                    "exit_date":        date,
                    "exit_type":        exit_type,
                    "direction":        open_trade["direction"],
                    "entry_price_a":    open_trade["entry_price_a"],
                    "entry_price_b":    open_trade["entry_price_b"],
                    "exit_price_a":     close_a,
                    "exit_price_b":     close_b,
                    "shares_a":         open_trade["shares_a"],
                    "shares_b":         open_trade["shares_b"],
                    "hedge_ratio_used": open_trade["hedge_ratio_used"],
                    "pnl":              round(pnl, 4),
                    "pnl_pct":          round(pnl / total_capital, 6),
                })
                open_trade = None
                continue

        if open_trade is None and sig in ("long_spread", "short_spread"):
            close_a = df_ohlcv.loc[date, "close_a"]
            close_b = df_ohlcv.loc[date, "close_b"]
            direction = 1 if sig == "long_spread" else -1
            hr = hedge_ratio.loc[date] if rolling_mode else hedge_ratio

            b_a = float(market_beta_a.loc[date]) if market_beta_a is not None and date in market_beta_a.index else 1.0
            b_b = float(market_beta_b.loc[date]) if market_beta_b is not None and date in market_beta_b.index else 1.0

            V_a, V_b = compute_beta_neutral_allocation(total_capital, b_a, b_b)
            shares_a =  direction * V_a / close_a
            shares_b = -direction * V_b / close_b

            open_trade = {
                "entry_date":       date,
                "direction":        direction,
                "entry_price_a":    close_a,
                "entry_price_b":    close_b,
                "shares_a":         shares_a,
                "shares_b":         shares_b,
                "hedge_ratio_used": hr,
                "market_beta_a":    b_a,
                "market_beta_b":    b_b,
                "bars_held":        0,
            }

    if not trades:
        cols = [
            "entry_date", "exit_date", "exit_type", "direction",
            "entry_price_a", "entry_price_b", "exit_price_a", "exit_price_b",
            "shares_a", "shares_b", "hedge_ratio_used",
            "market_beta_a", "market_beta_b", "pnl", "pnl_pct",
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
    market_beta_a: pd.Series = None,
    market_beta_b: pd.Series = None,
    max_hold_bars: int = None,
    max_loss_pct: float = None,
) -> tuple:
    """
    Run the full pairs backtest pipeline.

    Returns
    -------
    (trades, equity_curve, metrics) — three objects for downstream display.
    """
    starting_capital = 2 * capital_per_leg

    trades = build_trade_log(
        signals_df, df_ohlcv, hedge_ratio, capital_per_leg,
        market_beta_a=market_beta_a,
        market_beta_b=market_beta_b,
        max_hold_bars=max_hold_bars,
        max_loss_pct=max_loss_pct,
    )
    equity_curve = run_backtest(trades, starting_capital)
    metrics = compute_metrics(equity_curve, trades, starting_capital)

    return trades, equity_curve, metrics

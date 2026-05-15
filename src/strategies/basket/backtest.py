"""Basket / ETF arbitrage backtest — spread-based P&L."""

import numpy as np
import pandas as pd


def run_basket_backtest(
    signals_df: pd.DataFrame,
    spread: pd.Series,
    capital: float = 20_000.0,
    cost_bps: float = 5.0,
    n_stocks: int = 1,
) -> tuple:
    """
    Spread-based backtest for basket/ETF arbitrage.

    The spread is in log-price units (e.g. 0.01 = 1% basis deviation).
    Position sizing: notional = capital so that a 1% basis move earns 1% of capital.

    cost_bps is scaled by sqrt(n_stocks / 5) to reflect execution overhead when
    trading many instruments simultaneously (timing risk across 10-13 names vs.
    the baseline assumption of ~5).

    Returns
    -------
    (trades_df, equity_curve, metrics)
    """
    import math as _math
    from src.backtest.metrics import compute_metrics

    notional  = capital  # spread is fractional/log-price: 0.01 spread move = 1% of capital
    # Scale cost by sqrt(n_stocks / 5): 5 stocks = 1x, 10 stocks = 1.41x, 20 stocks = 2x
    cost_scale = _math.sqrt(max(n_stocks, 1) / 5.0)
    cost_rate  = cost_bps / 10_000 * cost_scale

    trades   = []
    open_pos = None

    for date, row in signals_df.iterrows():
        sig = row["signal"]
        s   = spread.get(date, np.nan)
        if np.isnan(s):
            continue

        if open_pos is not None:
            unrealized = open_pos["direction"] * (s - open_pos["entry_spread"]) * notional

            exit_type = None
            if sig in ("exit", "stop"):
                exit_type = sig
            if exit_type:
                gross = unrealized
                cost  = capital * cost_rate  # entry + exit cost
                pnl   = round(gross - cost, 4)
                trades.append({
                    "entry_date":   open_pos["entry_date"],
                    "exit_date":    date,
                    "exit_type":    exit_type,
                    "direction":    open_pos["direction"],
                    "entry_spread": open_pos["entry_spread"],
                    "exit_spread":  s,
                    "pnl":          pnl,
                    "pnl_pct":      round(pnl / capital, 6),
                })
                open_pos = None
                continue

        if open_pos is None and sig in ("long_spread", "short_spread"):
            open_pos = {
                "entry_date":   date,
                "direction":    1 if sig == "long_spread" else -1,
                "entry_spread": s,
            }

    if not trades:
        eq = pd.DataFrame(
            {"equity": [capital]},
            index=pd.DatetimeIndex([pd.Timestamp.today().normalize()], name="date"),
        )
        return pd.DataFrame(), eq, _empty_metrics()

    trades_df = pd.DataFrame(trades)

    # Build proper mark-to-market equity: track open positions day-by-day so that
    # unrealised losses while a trade is open appear in the equity curve.
    all_dates = pd.bdate_range(
        start=trades_df["entry_date"].min(),
        end=trades_df["exit_date"].max(),
    )
    spread_aligned = spread.reindex(all_dates).ffill()

    # Daily net position (+1 long, -1 short, 0 flat)
    daily_pos = pd.Series(0.0, index=all_dates)
    for _, tr in trades_df.iterrows():
        # Position is live from the bar after entry through the exit bar
        mask = (all_dates > tr["entry_date"]) & (all_dates <= tr["exit_date"])
        daily_pos[mask] += tr["direction"]

    # Daily P&L = position * daily spread change * notional
    daily_mtm = daily_pos * spread_aligned.diff().fillna(0.0) * notional

    # Deduct transaction costs on the exit bar (same total cost as before)
    cost_per_trade = capital * cost_rate
    exit_costs = trades_df.groupby("exit_date").size() * cost_per_trade
    daily_mtm = daily_mtm.subtract(exit_costs.reindex(all_dates, fill_value=0.0))

    equity_series = capital + daily_mtm.cumsum()
    equity_series.index.name = "date"
    equity_curve = equity_series.to_frame("equity")

    metrics = compute_metrics(equity_curve, trades_df, capital)
    return trades_df, equity_curve, metrics


def _empty_metrics() -> dict:
    return {
        "total_return":  0.0,
        "cagr":          0.0,
        "sharpe":        0.0,
        "sortino":       0.0,
        "max_drawdown":  0.0,
        "calmar":        float("nan"),
        "n_trades":      0,
        "win_rate":      float("nan"),
        "avg_win":       float("nan"),
        "avg_loss":      float("nan"),
        "profit_factor": float("nan"),
        "avg_hold_days": float("nan"),
    }

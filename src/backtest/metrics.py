"""Performance metrics computed from an equity curve and trade log."""

import math

import numpy as np
import pandas as pd


def compute_metrics(
    equity_curve: pd.DataFrame,
    trades: pd.DataFrame,
    starting_capital: float,
) -> dict:
    """
    Compute standard performance statistics.

    Parameters
    ----------
    equity_curve : DataFrame with column 'equity', indexed by date.
    trades       : Trade log DataFrame with columns including 'pnl',
                   'entry_date', 'exit_date', 'exit_type'.
    starting_capital : Initial portfolio value.

    Returns
    -------
    dict with keys: total_return, cagr, sharpe, max_drawdown, n_trades,
    win_rate, avg_win, avg_loss, profit_factor, avg_hold_days.
    """
    empty = {
        "total_return": 0.0, "cagr": 0.0, "sharpe": 0.0,
        "max_drawdown": 0.0, "n_trades": 0,
        "win_rate": float("nan"), "avg_win": float("nan"),
        "avg_loss": float("nan"), "profit_factor": float("nan"),
        "avg_hold_days": float("nan"),
    }

    if trades.empty or equity_curve.empty:
        return empty

    equity = equity_curve["equity"]
    n_days = len(equity)
    final = float(equity.iloc[-1])

    # ── Return metrics ────────────────────────────────────────────────────────
    total_return = (final - starting_capital) / starting_capital
    cagr = (final / starting_capital) ** (252.0 / n_days) - 1 if n_days > 1 else 0.0

    daily_returns = equity.pct_change().dropna()
    if len(daily_returns) >= 2 and daily_returns.std() > 0:
        sharpe = float(daily_returns.mean() / daily_returns.std() * math.sqrt(252))
    else:
        sharpe = 0.0

    max_drawdown = float((equity / equity.cummax() - 1).min())

    # ── Trade metrics ─────────────────────────────────────────────────────────
    n_trades = len(trades)
    wins = trades[trades["pnl"] > 0]["pnl"]
    losses = trades[trades["pnl"] <= 0]["pnl"]

    win_rate = len(wins) / n_trades if n_trades > 0 else float("nan")
    avg_win = float(wins.mean()) if not wins.empty else float("nan")
    avg_loss = float(losses.mean()) if not losses.empty else float("nan")

    if not wins.empty and not losses.empty and losses.sum() != 0:
        profit_factor = float(wins.sum() / abs(losses.sum()))
    elif not wins.empty and losses.empty:
        profit_factor = float("inf")
    else:
        profit_factor = float("nan")

    hold_days = (
        (pd.to_datetime(trades["exit_date"]) - pd.to_datetime(trades["entry_date"]))
        .dt.days
    )
    avg_hold_days = float(hold_days.mean()) if not hold_days.empty else float("nan")

    return {
        "total_return":  total_return,
        "cagr":          cagr,
        "sharpe":        sharpe,
        "max_drawdown":  max_drawdown,
        "n_trades":      n_trades,
        "win_rate":      win_rate,
        "avg_win":       avg_win,
        "avg_loss":      avg_loss,
        "profit_factor": profit_factor,
        "avg_hold_days": avg_hold_days,
    }

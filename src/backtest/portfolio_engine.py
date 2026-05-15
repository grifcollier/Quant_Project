"""Daily mark-to-market portfolio backtest for continuously-rebalanced strategies."""

import math

import numpy as np
import pandas as pd


def run_portfolio_backtest(
    positions_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    capital: float,
    cost_bps: float = 5.0,
    weights_df: pd.DataFrame = None,
) -> tuple:
    """
    Compute a daily equity curve from a positions DataFrame.

    Each bar's return is: sum_i( weight[t-1, i] * daily_return[t, i] )
    where weight[t, i] = position[t, i] / n_active[t]  (equal-weight among active positions).

    Parameters
    ----------
    positions_df : (T, N) DataFrame, values in {-1, 0, +1}, indexed by date.
    prices_df    : (T, N) DataFrame of closing prices, indexed by date.
    capital      : Total portfolio capital.
    cost_bps     : Transaction cost per unit of turnover (basis points).
    weights_df   : Optional (T, N) float weights. When provided, used directly instead
                   of the default equal-weight normalisation. Supports leverage (|w|>1 sum).

    Returns
    -------
    (equity_curve, metrics)
      equity_curve : DataFrame with column 'equity', indexed by date.
      metrics      : dict compatible with compute_metrics() output keys.
    """
    common = positions_df.index.intersection(prices_df.index)
    if common.empty:
        eq = pd.DataFrame({"equity": [capital]},
                          index=pd.DatetimeIndex([pd.Timestamp.today().normalize()], name="date"))
        return eq, _empty_metrics()

    pos = positions_df.loc[common].copy()
    px  = prices_df.loc[common].copy()

    if weights_df is not None:
        weights = weights_df.reindex(common).fillna(0.0)
    else:
        n_active = pos.abs().sum(axis=1)
        weights  = pos.div(n_active.replace(0, np.nan), axis=0).fillna(0.0)

    daily_ret = px.pct_change().fillna(0.0)

    port_ret = (weights.shift(1).fillna(0.0) * daily_ret).sum(axis=1)

    # Transaction cost proportional to absolute weight change (turnover)
    turnover = weights.diff().fillna(0.0).abs().sum(axis=1)
    cost     = turnover * cost_bps / 10_000

    net_ret = port_ret - cost
    equity_series = capital * (1.0 + net_ret).cumprod()
    equity_series.index.name = "date"
    equity_curve = equity_series.to_frame("equity")

    metrics = _compute_metrics(equity_curve, capital)
    return equity_curve, metrics


def _compute_metrics(equity_curve: pd.DataFrame, starting_capital: float) -> dict:
    equity   = equity_curve["equity"]
    n_days   = len(equity)
    final    = float(equity.iloc[-1])

    total_return = (final - starting_capital) / starting_capital
    cagr = (final / starting_capital) ** (252.0 / n_days) - 1 if n_days > 1 else 0.0

    daily_returns = equity.pct_change().dropna()
    if len(daily_returns) >= 2 and daily_returns.std() > 0:
        sharpe = float(daily_returns.mean() / daily_returns.std() * math.sqrt(252))
    else:
        sharpe = 0.0

    downside = daily_returns[daily_returns < 0].std()
    sortino  = float(daily_returns.mean() / downside * math.sqrt(252)) if downside > 0 else 0.0

    max_drawdown = float((equity / equity.cummax() - 1).min())
    calmar       = cagr / abs(max_drawdown) if max_drawdown < 0 else float("nan")

    return {
        "total_return":  total_return,
        "cagr":          cagr,
        "sharpe":        sharpe,
        "sortino":       sortino,
        "max_drawdown":  max_drawdown,
        "calmar":        calmar,
        "n_trades":      0,
        "win_rate":      float("nan"),
        "avg_win":       float("nan"),
        "avg_loss":      float("nan"),
        "profit_factor": float("nan"),
        "avg_hold_days": float("nan"),
    }


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

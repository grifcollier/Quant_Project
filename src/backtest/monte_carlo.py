"""Monte Carlo bootstrap for basket strategy backtests."""

import numpy as np
import pandas as pd


def bootstrap_trades(
    trades_df: pd.DataFrame,
    capital: float = 20_000.0,
    n_sims: int = 5_000,
    seed: int = 42,
) -> dict:
    """
    Trade-level bootstrap for single-ETF basket backtests.

    Resamples trades_df["pnl"] with replacement to produce a distribution
    of possible outcomes given different luck on trade ordering.

    Parameters
    ----------
    trades_df : Output of run_basket_backtest() — must contain "pnl" column.
    capital   : Starting capital (for return and drawdown calculations).
    n_sims    : Number of bootstrap simulations.
    seed      : Random seed for reproducibility.

    Returns
    -------
    dict with keys: sharpes, drawdowns, returns, equity_paths, n_sims,
                    n_trades, capital.
    """
    rng     = np.random.default_rng(seed)
    pnl     = trades_df["pnl"].values
    n       = len(pnl)
    n_store = min(500, n_sims)

    # Estimate annualized trade frequency to get a meaningful Sharpe
    if "entry_date" in trades_df.columns and "exit_date" in trades_df.columns and n > 1:
        span_days = (trades_df["exit_date"].max() - trades_df["entry_date"].min()).days
        n_per_year = n * 365.0 / max(span_days, 1)
    else:
        n_per_year = n

    sharpes   = np.empty(n_sims)
    drawdowns = np.empty(n_sims)
    returns   = np.empty(n_sims)
    paths     = np.empty((n_store, n + 1))

    for i in range(n_sims):
        idx      = rng.integers(0, n, size=n)
        sampled  = pnl[idx]
        equity   = np.empty(n + 1)
        equity[0] = capital
        np.cumsum(sampled, out=equity[1:])
        equity[1:] += capital

        ret = (equity[-1] - capital) / capital
        std = sampled.std()
        sr  = (sampled.mean() / std * np.sqrt(n_per_year)) if std > 1e-12 else 0.0
        peak = np.maximum.accumulate(equity)
        dd   = float(np.min(equity / peak - 1))

        sharpes[i]   = sr
        drawdowns[i] = dd
        returns[i]   = ret
        if i < n_store:
            paths[i] = equity

    return {
        "sharpes":      sharpes,
        "drawdowns":    drawdowns,
        "returns":      returns,
        "equity_paths": paths,
        "n_sims":       n_sims,
        "n_trades":     n,
        "capital":      capital,
    }


def bootstrap_returns(
    equity_curve: pd.DataFrame,
    capital: float = 20_000.0,
    n_sims: int = 5_000,
    seed: int = 42,
) -> dict:
    """
    Daily-returns bootstrap for basket-multi combined portfolio.

    Resamples the combined portfolio's daily return series with replacement,
    preserving cross-leg correlation by treating the portfolio as a whole.

    Parameters
    ----------
    equity_curve : DataFrame with "equity" column (output of basket-multi).
    capital      : Starting capital.
    n_sims       : Number of bootstrap simulations.
    seed         : Random seed for reproducibility.

    Returns
    -------
    Same schema as bootstrap_trades() for compatibility with plot_monte_carlo().
    n_trades field contains the number of trading days (not trade count).
    """
    rng          = np.random.default_rng(seed)
    daily_rets   = equity_curve["equity"].pct_change().dropna().values
    n            = len(daily_rets)
    n_store      = min(500, n_sims)

    sharpes   = np.empty(n_sims)
    drawdowns = np.empty(n_sims)
    returns   = np.empty(n_sims)
    paths     = np.empty((n_store, n + 1))

    for i in range(n_sims):
        idx     = rng.integers(0, n, size=n)
        sampled = daily_rets[idx]
        equity  = np.empty(n + 1)
        equity[0] = capital
        equity[1:] = capital * np.cumprod(1.0 + sampled)

        ret = (equity[-1] - capital) / capital
        std = sampled.std()
        sr  = (sampled.mean() / std * np.sqrt(252)) if std > 1e-12 else 0.0
        peak = np.maximum.accumulate(equity)
        dd   = float(np.min(equity / peak - 1))

        sharpes[i]   = sr
        drawdowns[i] = dd
        returns[i]   = ret
        if i < n_store:
            paths[i] = equity

    return {
        "sharpes":      sharpes,
        "drawdowns":    drawdowns,
        "returns":      returns,
        "equity_paths": paths,
        "n_sims":       n_sims,
        "n_trades":     n,
        "capital":      capital,
    }

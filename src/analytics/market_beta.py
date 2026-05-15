"""Rolling market beta estimation using OLS of stock returns vs a market proxy."""

import numpy as np
import pandas as pd


def compute_market_beta(
    price_series: pd.Series,
    market_series: pd.Series,
    window: int = 252,
) -> pd.Series:
    """
    Estimate rolling market beta: how much the stock moves per 1% market move.

    Uses OLS: β = Cov(stock_returns, market_returns) / Var(market_returns)
    over a rolling window. Values before the window warms up default to 1.0
    (assumes the stock moves in line with the market until there is data).

    Parameters
    ----------
    price_series  : Closing prices for the stock.
    market_series : Closing prices for the market proxy (e.g. SPY).
    window        : Rolling window in trading days (default: 252 = 1 year).

    Returns
    -------
    pd.Series of beta estimates, same index as price_series.
    """
    stock_ret  = price_series.pct_change()
    market_ret = market_series.reindex(stock_ret.index).pct_change()

    rolling_cov = stock_ret.rolling(window).cov(market_ret)
    rolling_var = market_ret.rolling(window).var()

    beta = (rolling_cov / rolling_var).clip(lower=0.1)
    beta = beta.fillna(1.0)
    beta.name = f"market_beta_{price_series.name or 'stock'}"
    return beta


def compute_beta_neutral_allocation(
    total_capital: float,
    beta_a: float,
    beta_b: float,
) -> tuple:
    """
    Solve for dollar allocations that are simultaneously dollar-neutral
    and beta-neutral.

    Constraints
    -----------
    (1) V_a + V_b = total_capital          (full capital deployed)
    (2) V_a * beta_a = V_b * beta_b        (zero net market exposure)

    Solution
    --------
    V_a = total_capital * beta_b / (beta_a + beta_b)
    V_b = total_capital * beta_a / (beta_a + beta_b)

    Returns (V_a, V_b) — positive dollar values for each leg.
    When beta_a == beta_b the result is equal dollar splits (dollar-neutral).
    """
    denom = beta_a + beta_b
    V_a = total_capital * beta_b / denom
    V_b = total_capital * beta_a / denom
    return V_a, V_b

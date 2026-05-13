"""Spread construction via OLS hedge ratio on log-prices."""

import numpy as np
import pandas as pd
import statsmodels.api as sm


def compute_hedge_ratio(series_a: pd.Series, series_b: pd.Series) -> float:
    """
    Estimate the hedge ratio β by regressing log(A) on log(B).

    The spread is defined as: log(A) - β * log(B)

    A hedge ratio > 1 means A moves more than B per unit; you'd hold fewer
    shares of A relative to B to keep the position dollar-neutral.
    """
    log_a = np.log(series_a)
    log_b = np.log(series_b)

    log_b_with_const = sm.add_constant(log_b)
    model = sm.OLS(log_a, log_b_with_const).fit()

    beta = model.params.iloc[1]
    return float(beta)


def compute_spread(series_a: pd.Series, series_b: pd.Series, hedge_ratio: float) -> pd.Series:
    """
    Compute the log-price spread: log(A) - β * log(B).

    A stationary spread is the core assumption of pairs trading — when it
    deviates far from its mean, we expect it to revert.
    """
    spread = np.log(series_a) - hedge_ratio * np.log(series_b)
    spread.name = "spread"
    return spread


def compute_rolling_hedge_ratio(
    series_a: pd.Series, series_b: pd.Series, window: int = 252
) -> pd.Series:
    """
    Estimate a time-varying hedge ratio using rolling OLS (vectorised).

    At each date t, the beta is computed from the prior `window` observations
    only — no future data is used. The first (window - 1) values are NaN.

    Uses the identity: β = Cov(log_a, log_b) / Var(log_b), which is the OLS
    slope estimator without requiring a Python loop.
    """
    log_a = np.log(series_a)
    log_b = np.log(series_b)
    rolling_cov = log_a.rolling(window).cov(log_b)
    rolling_var = log_b.rolling(window).var()
    betas = (rolling_cov / rolling_var).rename("rolling_beta")
    return betas


def compute_rolling_spread(
    series_a: pd.Series, series_b: pd.Series, rolling_hr: pd.Series
) -> pd.Series:
    """
    Compute a rolling-beta-adjusted spread: log(A) - rolling_β(t) * log(B).

    Leading NaN rows (from the rolling window warm-up) are dropped so the
    returned series starts from the first date with a valid beta estimate.
    """
    log_a  = np.log(series_a)
    log_b  = np.log(series_b)
    spread = (log_a - rolling_hr * log_b).dropna()
    spread.name = "spread"
    return spread

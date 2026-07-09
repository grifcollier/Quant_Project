"""Statistical tests for time-series stationarity and mean-reversion speed."""

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller


def adf_test(series: pd.Series) -> dict:
    """
    Augmented Dickey-Fuller test for stationarity of a time series.

    The null hypothesis is that the series has a unit root (i.e. is NOT
    stationary). A p-value < 0.05 lets us reject that null — meaning the
    series is stationary and mean-reversion logic applies.

    Returns:
        adf_stat:       test statistic (more negative = stronger rejection)
        p_value:        probability of observing this stat under the null
        is_stationary:  True if p_value < 0.05
    """
    result = adfuller(series.dropna(), autolag="AIC")
    return {
        "adf_stat": round(float(result[0]), 4),
        "p_value": round(float(result[1]), 4),
        "is_stationary": bool(result[1] < 0.05),
    }


def compute_half_life(series: pd.Series) -> float:
    """
    Estimate the half-life of mean reversion from an AR(1) model.

    Fit: Δseries_t = α * series_{t-1} + ε
    Half-life = -ln(2) / α  (in trading days)

    This tells you roughly how many days it takes for the series to revert
    halfway to its mean — a useful guide for choosing a rolling window
    and holding period. Typical swing-trading pairs: 10–40 days.
    """
    series = series.dropna()
    lagged = series.shift(1).dropna()
    delta = series.diff().dropna()

    lagged, delta = lagged.align(delta, join="inner")

    alpha = np.polyfit(lagged, delta, 1)[0]

    if alpha >= 0:
        return float("inf")

    half_life = -np.log(2) / alpha
    return round(float(half_life), 1)


def stationarity_gate(
    baseline_spread: pd.Series,
    alternative_spread: pd.Series,
    significance: float = 0.10,
    min_obs: int = 10,
) -> dict:
    """
    Compare spread stationarity between a baseline and an alternative fitting method.

    Returns whether the alternative *breaks* stationarity the baseline has — the
    condition tested in walk-forward Phase 3 (July 2026) when evaluating ridge vs
    OLS: if OLS spread is stationary but the alternative's spread is not, the
    method under test has degraded a tradeable signal.

    Parameters
    ----------
    baseline_spread    : Spread from the reference method (e.g. plain OLS).
    alternative_spread : Spread from the method under test (e.g. ridge, NNLS).
    significance       : ADF p-value threshold for declaring a spread stationary
                         (default: 0.10 — the Phase 3 gate level).
    min_obs            : Minimum non-NaN observations required to run ADF; returns
                         NaN p-values and alert=False if either series is too short.

    Returns
    -------
    dict with keys:
        baseline_pval          : ADF p-value for the baseline spread (float or nan)
        alternative_pval       : ADF p-value for the alternative spread (float or nan)
        baseline_stationary    : True if baseline_pval < significance
        alternative_stationary : True if alternative_pval < significance
        alert                  : True when baseline is stationary but alternative is NOT
    """
    def _pval(s):
        s = s.dropna()
        if len(s) < min_obs:
            return float("nan")
        return round(float(adfuller(s, autolag="AIC")[1]), 4)

    bp = _pval(baseline_spread)
    ap = _pval(alternative_spread)
    b_stat = (not np.isnan(bp)) and bp < significance
    a_stat = (not np.isnan(ap)) and ap < significance
    return {
        "baseline_pval":          bp,
        "alternative_pval":       ap,
        "baseline_stationary":    b_stat,
        "alternative_stationary": a_stat,
        "alert":                  b_stat and not a_stat,
    }

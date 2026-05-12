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

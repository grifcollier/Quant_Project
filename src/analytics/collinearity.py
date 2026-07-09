"""Rolling collinearity diagnostics for basket/ETF regression fits."""

import numpy as np
import pandas as pd


def compute_rolling_condition_numbers(
    constituent_prices: pd.DataFrame,
    window: int,
) -> pd.Series:
    """
    Causal rolling condition number of the stock log-return correlation matrix.

    At each bar t >= window, fits on log-returns in [t-window : t] — identical
    look-back convention to rolling_basket_spread. No look-ahead.

    Returns pd.Series indexed same as constituent_prices, NaN for warmup bars.
    """
    log_ret = np.log(constituent_prices).diff().values
    n = len(constituent_prices)
    values = np.full(n, np.nan)

    for t in range(window, n):
        ret_window = log_ret[t - window : t]
        valid = ~np.isnan(ret_window).any(axis=1)
        r = ret_window[valid]
        if len(r) < 2:
            continue
        corr = np.corrcoef(r.T)
        eigvals = np.linalg.eigvalsh(corr)
        min_eig = eigvals[0]
        if min_eig <= 0:
            values[t] = np.inf
        else:
            values[t] = eigvals[-1] / min_eig

    return pd.Series(values, index=constituent_prices.index, name="condition_number")


def compute_vif(returns_df: pd.DataFrame) -> dict:
    """
    Variance Inflation Factor for each stock given a fixed returns window.

    For each stock, regresses it on all others via OLS and computes
    VIF = 1 / (1 - R²). VIF > 10 indicates high collinearity.

    Parameters
    ----------
    returns_df : DataFrame of log returns, shape (n_obs, n_stocks).

    Returns
    -------
    dict of {ticker: vif_value}
    """
    X = returns_df.values
    result = {}
    for i, col in enumerate(returns_df.columns):
        y = X[:, i]
        others = np.delete(X, i, axis=1)
        aug = np.column_stack([np.ones(len(others)), others])
        coeffs, _, _, _ = np.linalg.lstsq(aug, y, rcond=None)
        y_hat = aug @ coeffs
        ss_res = ((y - y_hat) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        result[col] = 1.0 / (1.0 - r2) if r2 < 1.0 else float("inf")
    return result

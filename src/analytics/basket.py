"""OLS basket / ETF spread construction using log-prices."""

import numpy as np
import pandas as pd


def fit_basket(
    etf_prices: pd.Series,
    constituent_prices: pd.DataFrame,
) -> tuple:
    """
    Fit OLS: log(ETF) ~ intercept + b1*log(S1) + ... + bN*log(SN).

    Returns (coefficients, intercept, spread).
    """
    y = np.log(etf_prices.values).astype(float)
    X = np.log(constituent_prices.values).astype(float)
    X_aug = np.column_stack([np.ones(len(X)), X])

    result, _, _, _ = np.linalg.lstsq(X_aug, y, rcond=None)
    intercept    = float(result[0])
    coefficients = result[1:]

    fitted = X @ coefficients + intercept
    spread = pd.Series(y - fitted, index=etf_prices.index, name="basket_spread")
    return coefficients, intercept, spread


def rolling_basket_spread(
    etf_prices: pd.Series,
    constituent_prices: pd.DataFrame,
    window: int,
    ridge_alpha: float = 0.0,
    regime_filter: float = 0.0,
) -> pd.Series:
    """
    Rolling out-of-sample basket spread.

    At each bar t >= window:
      1. Fit regression on log-prices in [t-window : t] (out-of-sample at t).
      2. Evaluate residual at bar t using the fitted coefficients.

    Parameters
    ----------
    ridge_alpha    : L2 regularisation strength (0 = plain OLS).
                     Penalises large constituent weights, reducing overfitting
                     when n_params/n_obs is high (e.g. 13 stocks, 60-bar window).
                     A value of 0.05–0.20 is a reasonable starting point.
    regime_filter  : If > 0, suppress the spread (set to NaN) whenever the
                     normalised L2 change in OLS coefficients from the previous
                     bar exceeds this threshold.  Detects structural breaks where
                     the basket relationship has genuinely shifted rather than
                     temporarily deviated.  Try 0.20–0.50.

    Returns
    -------
    pd.Series with same index as etf_prices. Rows 0..window-1 are NaN.
    Bars suppressed by the regime filter are also NaN.
    """
    n = len(etf_prices)
    values = np.full(n, np.nan)

    y_all = np.log(etf_prices.values).astype(float)
    X_all = np.log(constituent_prices.values).astype(float)

    prev_coefs = None

    for t in range(window, n):
        y_train = y_all[t - window : t]
        X_train = X_all[t - window : t]
        X_aug   = np.column_stack([np.ones(window), X_train])

        if ridge_alpha > 0:
            XtX   = X_aug.T @ X_aug
            # Scale penalty by mean diagonal so alpha is unit-invariant
            scale = np.trace(XtX) / X_aug.shape[1]
            A     = XtX + ridge_alpha * scale * np.eye(X_aug.shape[1])
            A[0, 0] -= ridge_alpha * scale  # don't penalise intercept
            coeffs = np.linalg.solve(A, X_aug.T @ y_train)
        else:
            coeffs, _, _, _ = np.linalg.lstsq(X_aug, y_train, rcond=None)

        curr_coefs = coeffs[1:]

        # Regime filter: skip this bar if basket weights have shifted too rapidly
        if regime_filter > 0 and prev_coefs is not None:
            ref_norm = np.linalg.norm(prev_coefs)
            if ref_norm > 1e-10:
                shift = np.linalg.norm(curr_coefs - prev_coefs) / ref_norm
                if shift > regime_filter:
                    prev_coefs = curr_coefs
                    continue  # values[t] stays NaN — no signal generated

        prev_coefs = curr_coefs
        values[t]  = y_all[t] - (X_all[t] @ curr_coefs + float(coeffs[0]))

    return pd.Series(values, index=etf_prices.index, name="basket_spread")

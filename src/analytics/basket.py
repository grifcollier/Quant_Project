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


_RIDGE_GRID = (0.1, 1.0, 10.0)


def rolling_basket_spread(
    etf_prices: pd.Series,
    constituent_prices: pd.DataFrame,
    window: int,
    ridge_alpha: float = 0.0,
    regime_filter: float = 0.0,
    ridge_threshold: float = 0.0,
    return_diagnostics: bool = False,
) -> "pd.Series | tuple":
    """
    Rolling out-of-sample basket spread.

    At each bar t >= window:
      1. Fit regression on log-prices in [t-window : t] (out-of-sample at t).
      2. Evaluate residual at bar t using the fitted coefficients.

    Parameters
    ----------
    ridge_alpha     : Fixed L2 regularisation strength (0 = plain OLS).
                      Ignored when ridge_threshold > 0 (dynamic mode takes over).
    regime_filter   : If > 0, suppress the spread (set to NaN) whenever the
                      normalised L2 change in OLS coefficients from the previous
                      bar exceeds this threshold.  Try 0.20–0.50.
    ridge_threshold : If > 0, enables per-window dynamic ridge switching.
                      At each bar the condition number of the return correlation
                      matrix is computed; if it exceeds this threshold, the
                      smallest alpha from {0.1, 1.0, 10.0} that brings the
                      condition number below the threshold is used (capped at
                      10.0 if none suffice). When 0 (default), behaviour is
                      identical to the original implementation.
    return_diagnostics : If True, return (spread, cond_num_series) instead of
                         just spread. cond_num_series contains the raw condition
                         number at each bar (NaN for warmup and plain-OLS bars).

    Returns
    -------
    pd.Series with same index as etf_prices (rows 0..window-1 are NaN), or
    (spread, cond_num_series) when return_diagnostics=True.
    """
    n = len(etf_prices)
    values    = np.full(n, np.nan)
    cond_nums = np.full(n, np.nan)  # populated only when ridge_threshold > 0

    y_all = np.log(etf_prices.values).astype(float)
    X_all = np.log(constituent_prices.values).astype(float)

    prev_coefs = None

    for t in range(window, n):
        y_train = y_all[t - window : t]
        X_train = X_all[t - window : t]
        X_aug   = np.column_stack([np.ones(window), X_train])

        # Determine effective ridge_alpha for this bar
        eff_alpha = ridge_alpha
        if ridge_threshold > 0:
            ret_window = np.diff(X_train, axis=0)           # log-returns: (window-1, n_stocks)
            if ret_window.shape[0] >= 2:
                corr    = np.corrcoef(ret_window.T)
                eigvals = np.linalg.eigvalsh(corr)
                min_eig = eigvals[0]
                cond    = eigvals[-1] / min_eig if min_eig > 0 else np.inf
                cond_nums[t] = cond
                if cond > ridge_threshold:
                    # Find smallest grid alpha that brings X_train'X_train condition
                    # number below threshold; cap at grid maximum if none suffice.
                    XtX_s = X_train.T @ X_train
                    scale_s = np.trace(XtX_s) / X_train.shape[1]
                    eff_alpha = _RIDGE_GRID[-1]             # default: cap
                    for a in _RIDGE_GRID:
                        A_s = XtX_s + a * scale_s * np.eye(X_train.shape[1])
                        ev  = np.linalg.eigvalsh(A_s)
                        if ev[0] > 0 and ev[-1] / ev[0] <= ridge_threshold:
                            eff_alpha = a
                            break

        if eff_alpha > 0:
            XtX   = X_aug.T @ X_aug
            scale = np.trace(XtX) / X_aug.shape[1]
            A     = XtX + eff_alpha * scale * np.eye(X_aug.shape[1])
            A[0, 0] -= eff_alpha * scale
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

    spread = pd.Series(values, index=etf_prices.index, name="basket_spread")
    if return_diagnostics:
        cond_series = pd.Series(cond_nums, index=etf_prices.index, name="condition_number")
        return spread, cond_series
    return spread

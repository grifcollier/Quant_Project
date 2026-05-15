"""PCA decomposition for multi-asset statistical arbitrage."""

import numpy as np
import pandas as pd


def fit_pca(returns_df: pd.DataFrame, n_components: int):
    """
    Fit PCA on a returns matrix.

    Uses numpy.linalg.eigh on the sample covariance matrix (no sklearn needed).
    Standardises each column before decomposition, then rescales residuals back.

    Parameters
    ----------
    returns_df   : (T, N) DataFrame of daily returns.
    n_components : Number of systematic factors to extract.

    Returns
    -------
    loadings   : (N, k) ndarray
    factors_df : (T, k) DataFrame of factor realisations
    resid_df   : (T, N) DataFrame of idiosyncratic residuals (return units)
    """
    k = min(n_components, returns_df.shape[1] - 1)
    R = returns_df.values.astype(float)

    means = R.mean(axis=0)
    stds  = R.std(axis=0, ddof=1)
    stds  = np.where(stds == 0, 1.0, stds)
    R_std = (R - means) / stds

    cov = np.cov(R_std.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    idx = np.argsort(eigenvalues)[::-1]
    loadings = eigenvectors[:, idx[:k]]      # (N, k)

    factors      = R_std @ loadings           # (T, k)
    systematic   = factors @ loadings.T       # (T, N) — standardised
    resid_std    = R_std - systematic
    resid        = resid_std * stds           # rescale to return units

    factors_df = pd.DataFrame(factors, index=returns_df.index,
                               columns=[f"F{i+1}" for i in range(k)])
    resid_df   = pd.DataFrame(resid,   index=returns_df.index,
                               columns=returns_df.columns)
    return loadings, factors_df, resid_df


def rolling_pca_residuals(
    returns_df: pd.DataFrame,
    window: int,
    n_components: int,
) -> pd.DataFrame:
    """
    Compute rolling out-of-sample PCA residuals with no look-ahead.

    At each bar t (t >= window):
      1. Fit PCA on the trailing window [t-window : t].
      2. Project bar t's returns onto the fitted loading matrix.
      3. Store the residual (idiosyncratic component) for bar t.

    Returns
    -------
    DataFrame with same index/columns as returns_df.
    Rows 0..window-1 are NaN (insufficient history).
    """
    n_rows, n_cols = returns_df.shape
    k = min(n_components, n_cols - 1)
    residuals = np.full((n_rows, n_cols), np.nan)
    R = returns_df.values.astype(float)

    for t in range(window, n_rows):
        train = R[t - window : t]              # (window, N)
        means = train.mean(axis=0)
        stds  = train.std(axis=0, ddof=1)
        stds  = np.where(stds == 0, 1.0, stds)

        train_std = (train - means) / stds
        cov = np.cov(train_std.T)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        idx = np.argsort(eigenvalues)[::-1]
        loadings = eigenvectors[:, idx[:k]]    # (N, k)

        r_t       = R[t]
        r_t_std   = (r_t - means) / stds
        f_t       = r_t_std @ loadings         # (k,)
        sys_t     = f_t @ loadings.T           # (N,) — systematic component
        e_t_std   = r_t_std - sys_t
        residuals[t] = e_t_std * stds          # rescale to return units

    return pd.DataFrame(residuals, index=returns_df.index, columns=returns_df.columns)

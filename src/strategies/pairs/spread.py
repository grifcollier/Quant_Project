"""Spread construction: static OLS, rolling OLS, and Kalman-filter hedge ratios."""

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


def compute_kalman_hedge_ratio(
    series_a: pd.Series,
    series_b: pd.Series,
    delta: float = 1e-4,
    obs_noise: float = 1e-3,
    init_window: int = 60,
) -> pd.DataFrame:
    """
    Estimate time-varying alpha and beta using a Kalman filter.

    State vector: [alpha_t, beta_t]
    Observation:  log(A)_t = alpha_t + beta_t * log(B)_t + v,   v ~ N(0, R)
    Transition:   state follows a random walk (F = I),           w ~ N(0, Q)

    The filter is seeded with an OLS estimate on the first `init_window` bars
    so the spread is stationary from bar 0 with no convergence artefact.

    Parameters
    ----------
    delta       : Process noise intensity — Q = delta/(1-delta) * I.
                  Higher → faster adaptation to regime changes, noisier beta.
                  Typical range: 1e-5 (very slow) to 1e-3 (fast).
    obs_noise   : Observation noise variance R. Higher → smoother estimates.
    init_window : Number of bars used for the OLS seed (default: 60).

    Returns
    -------
    DataFrame with columns ['alpha', 'beta'], indexed identically to inputs.
    """
    log_a = np.log(series_a).values
    log_b = np.log(series_b).values
    n = len(log_a)

    Q = delta / (1.0 - delta) * np.eye(2)
    R = float(obs_noise)

    # Seed state with OLS on the first init_window bars
    seed = min(init_window, n)
    X_seed = np.column_stack([np.ones(seed), log_b[:seed]])
    ols_coef, *_ = np.linalg.lstsq(X_seed, log_a[:seed], rcond=None)
    state = ols_coef.copy()  # [alpha, beta]
    P     = np.zeros((2, 2))

    alphas = np.empty(n)
    betas  = np.empty(n)

    for t in range(n):
        H = np.array([1.0, log_b[t]])

        P_pred     = P + Q
        innovation = log_a[t] - H @ state
        S          = H @ P_pred @ H + R
        K          = P_pred @ H / S

        state = state + K * innovation
        P     = (np.eye(2) - np.outer(K, H)) @ P_pred

        alphas[t] = state[0]
        betas[t]  = state[1]

    return pd.DataFrame({"alpha": alphas, "beta": betas}, index=series_a.index)


def compute_kalman_spread(
    series_a: pd.Series,
    series_b: pd.Series,
    kalman_params: pd.DataFrame,
) -> pd.Series:
    """
    Compute the Kalman-filtered spread: log(A) - alpha(t) - beta(t)*log(B).

    Because alpha adapts continuously to absorb level shifts, this spread is
    structurally mean-zero — unlike the OLS spread which can drift when the
    intercept is not modelled.
    """
    log_a  = np.log(series_a)
    log_b  = np.log(series_b)
    spread = log_a - kalman_params["alpha"] - kalman_params["beta"] * log_b
    spread.name = "spread"
    return spread.dropna()


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

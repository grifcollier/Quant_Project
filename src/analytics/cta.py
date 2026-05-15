"""EWMAC trend-following signals and vol-targeting for CTA / managed futures strategy."""

import numpy as np
import pandas as pd

_DEFAULT_PAIRS = ((8, 32), (16, 64), (32, 128), (64, 256))


def ewmac(prices: pd.Series, fast: int, slow: int) -> pd.Series:
    """
    Normalised EWMAC signal, capped at ±2.

    raw = EMA(fast) - EMA(slow)
    signal = raw / rolling_std(raw, window=slow), clipped to [-2, 2]
    """
    ema_fast = prices.ewm(span=fast, min_periods=fast).mean()
    ema_slow = prices.ewm(span=slow, min_periods=slow).mean()
    raw = ema_fast - ema_slow
    norm = raw / raw.rolling(slow).std().replace(0, np.nan)
    return norm.clip(-2, 2)


def combined_ewmac(
    prices: pd.Series,
    pairs: tuple = _DEFAULT_PAIRS,
) -> pd.Series:
    """Equal-weight mean of multiple EWMAC horizons."""
    signals = [ewmac(prices, f, s) for f, s in pairs]
    return pd.concat(signals, axis=1).mean(axis=1)


def instrument_vol(prices: pd.Series, span: int = 25) -> pd.Series:
    """Annualised EWM volatility of daily returns."""
    daily_ret = prices.pct_change()
    return daily_ret.ewm(span=span, min_periods=span).std() * np.sqrt(252)


def vol_targeted_weights(
    positions_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    tau: float = 0.20,
    vol_span: int = 25,
    weight_cap: float = None,
) -> pd.DataFrame:
    """
    Convert binary ±1 direction signals to vol-targeted weights.

    weight_i = direction_i × tau / (sigma_i × N_active)

    Each active instrument receives an equal share of the portfolio vol budget tau.
    With perfectly correlated instruments the gross exposure targets tau;
    with diversification, realised portfolio vol will be lower.

    Parameters
    ----------
    positions_df : binary {-1, 0, +1} directions, indexed by date.
    prices_df    : closing prices aligned to positions_df.index.
    tau          : annualised portfolio vol target (e.g. 0.20 = 20%).
    vol_span     : EWM span for per-instrument daily-return std (default 25 days).
    weight_cap   : optional per-instrument weight cap (e.g. 0.40 = 40% of capital).
    """
    px = prices_df.reindex(positions_df.index)
    n_active = positions_df.abs().sum(axis=1).replace(0, np.nan)

    vol_df = pd.DataFrame(
        {t: instrument_vol(px[t], span=vol_span) for t in positions_df.columns},
        index=positions_df.index,
    ).ffill().replace(0, np.nan)

    weights = positions_df * tau / (vol_df.mul(n_active, axis=0))

    if weight_cap is not None:
        weights = weights.clip(-abs(weight_cap), abs(weight_cap))

    return weights.fillna(0.0)

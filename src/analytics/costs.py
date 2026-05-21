"""Volume-adjusted transaction cost estimation."""

import numpy as np
import pandas as pd


def estimate_cost_bps(
    prices: pd.Series,
    volume: pd.Series,
    order_notional: float = 4_000.0,
    half_spread_bps: float = 0.5,
    adv_window: int = 20,
) -> pd.Series:
    """
    Rolling estimate of one-way transaction cost in basis points.

    cost_t = half_spread_bps + market_impact_t

    Market impact uses a simplified Kyle's lambda approximation:
        impact_t = 0.1 × daily_vol_t × sqrt(order_notional / ADV_t)

    where ADV_t = rolling(adv_window).mean(volume × prices).

    For liquid ETFs (SPY, QQQ) this produces ~0.5–1.5bps vs. the flat 5bps default.
    For less liquid single stocks it can reach 3–8bps.

    Parameters
    ----------
    prices         : daily closing prices.
    volume         : daily share volume (must align with prices index).
    order_notional : assumed dollar size of the order (default $4,000 per instrument).
    half_spread_bps: fixed half-spread component in bps (default 0.5bps for ETFs).
    adv_window     : rolling window for average daily dollar volume (default 20 days).

    Returns
    -------
    pd.Series of estimated cost in bps, same index as prices.
    """
    daily_vol = prices.pct_change().ewm(span=20).std()
    adv = (volume * prices).rolling(adv_window).mean()
    adv = adv.replace(0, np.nan)

    market_impact = 0.1 * daily_vol * np.sqrt(order_notional / adv)

    # Convert fractional impact to bps
    cost = half_spread_bps + market_impact * 10_000
    return cost.fillna(half_spread_bps)

"""Basket/ETF arbitrage signal generation — thin wrapper over pairs signals."""

import pandas as pd

from src.strategies.pairs.signals import compute_zscore, generate_signals


def generate_basket_signals(
    spread: pd.Series,
    window: int,
    z_entry: float = 2.0,
    z_exit: float  = 0.5,
    z_stop: float  = 3.0,
) -> tuple:
    """
    Z-score the basket spread and generate entry/exit signals.

    Returns
    -------
    (signals_df, zscore) — same types as generate_signals() and compute_zscore().
    """
    zscore  = compute_zscore(spread, window=window)
    signals = generate_signals(zscore, z_entry=z_entry, z_exit=z_exit, z_stop=z_stop)
    return signals, zscore

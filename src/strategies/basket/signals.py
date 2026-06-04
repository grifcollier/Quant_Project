"""Basket/ETF arbitrage signal generation — thin wrapper over pairs signals."""

import pandas as pd

from src.strategies.pairs.signals import compute_zscore, generate_signals


def generate_basket_signals(
    spread: pd.Series,
    window: int,
    z_entry: float = 2.0,
    z_exit: float  = 0.5,
    z_stop: float  = 3.0,
    vix_series: pd.Series | None = None,
    vix_threshold: float = 0.0,
) -> tuple:
    """
    Z-score the basket spread and generate entry/exit signals.

    Parameters
    ----------
    vix_series    : Daily VIX closing prices aligned to the spread index.
    vix_threshold : When > 0, entry signals are suppressed on days where
                    VIX > threshold by clipping the z-score inside the entry
                    bands before passing to the stateful signal generator.
                    Existing open positions can still exit normally.

    Returns
    -------
    (signals_df, zscore) — zscore is the original (unclipped) series for viz.
    """
    zscore = compute_zscore(spread, window=window)

    if vix_series is not None and vix_threshold > 0:
        vix_aligned = vix_series.reindex(zscore.index).ffill()
        mask = vix_aligned > vix_threshold
        zscore_for_signals = zscore.copy()
        zscore_for_signals[mask] = zscore_for_signals[mask].clip(
            -(z_entry - 0.01), z_entry - 0.01
        )
    else:
        zscore_for_signals = zscore

    signals = generate_signals(zscore_for_signals, z_entry=z_entry, z_exit=z_exit, z_stop=z_stop)
    return signals, zscore

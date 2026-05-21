"""Parameter sweep / grid search for the CTA strategy (diagnostic tool)."""

import math

import numpy as np
import pandas as pd

from src.analytics.cta import vol_targeted_weights
from src.backtest.portfolio_engine import run_portfolio_backtest
from src.strategies.cta.signals import generate_cta_positions


def sweep_cta_params(
    prices_df: pd.DataFrame,
    fold_starts: list,
    fold_ends: list,
    thresholds: list = None,
    vol_spans: list = None,
    signal_modes: list = None,
    tau: float = 0.20,
    cost_bps: float = 5.0,
    capital: float = 20_000.0,
) -> pd.DataFrame:
    """
    Grid search over CTA parameters across pre-computed walk-forward folds.

    Returns a DataFrame indexed by (threshold, vol_span, signal_mode) with columns:
    sharpe_mean, sharpe_std, cagr_mean, max_drawdown_mean, n_folds_run.
    """
    if thresholds is None:
        thresholds = [0.0, 0.1, 0.2, 0.3, 0.5]
    if vol_spans is None:
        vol_spans = [15, 25, 40, 60]
    if signal_modes is None:
        signal_modes = ["binary", "continuous"]

    pairs = ((8, 32), (16, 64), (32, 128), (64, 256))
    records = []

    total = len(thresholds) * len(vol_spans) * len(signal_modes)
    done = 0

    for signal_mode in signal_modes:
        # Pre-compute positions on full history once per (signal_mode) — saves recomputing per fold
        positions_full, _ = generate_cta_positions(
            prices_df, pairs=pairs, threshold=0.0, signal_mode=signal_mode
        )

        for vol_span in vol_spans:
            for threshold in thresholds:
                done += 1
                print(f"  [{done}/{total}] signal={signal_mode}  vol_span={vol_span}  threshold={threshold}", end="\r")

                # Apply threshold mask to pre-computed signals
                # Recompute with threshold since it modifies which positions are active
                positions_t, _ = generate_cta_positions(
                    prices_df, pairs=pairs, threshold=threshold, signal_mode=signal_mode
                )

                # Compute weights on full history for proper EWM warm-up
                weights_full = vol_targeted_weights(
                    positions_t, prices_df, tau=tau, vol_span=vol_span
                )

                sharpes, cagrs, dds = [], [], []

                for fold_start, fold_end in zip(fold_starts, fold_ends):
                    mask = (prices_df.index >= fold_start) & (prices_df.index <= fold_end)
                    if mask.sum() < 50:
                        continue

                    pos_fold = positions_t.loc[mask]
                    px_fold  = prices_df.loc[mask]
                    wt_fold  = weights_full.loc[mask]

                    _, m = run_portfolio_backtest(
                        pos_fold, px_fold, capital=capital,
                        cost_bps=cost_bps, weights_df=wt_fold,
                    )

                    sharpes.append(m["sharpe"])
                    cagrs.append(m["cagr"])
                    dds.append(m["max_drawdown"])

                if not sharpes:
                    continue

                records.append({
                    "threshold":       threshold,
                    "vol_span":        vol_span,
                    "signal_mode":     signal_mode,
                    "sharpe_mean":     float(np.mean(sharpes)),
                    "sharpe_std":      float(np.std(sharpes)),
                    "cagr_mean":       float(np.mean(cagrs)),
                    "max_drawdown_mean": float(np.mean(dds)),
                    "n_folds_run":     len(sharpes),
                })

    print()  # newline after progress indicator
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).set_index(["threshold", "vol_span", "signal_mode"])
    return df

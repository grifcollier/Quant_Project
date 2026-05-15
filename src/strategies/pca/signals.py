"""Signal generation for PCA statistical arbitrage."""

import numpy as np
import pandas as pd


def generate_pca_signals(
    residuals_df: pd.DataFrame,
    window: int,
    z_entry: float = 2.0,
    z_exit: float  = 0.5,
    z_stop: float  = 3.0,
    top_n: int     = 3,
) -> tuple:
    """
    Generate long/short positions from rolling z-scored PCA residuals.

    At each bar:
      - Long the up-to top_n stocks whose z-scores are below -z_entry.
      - Short the up-to top_n stocks whose z-scores are above +z_entry.
      - Exit a long when |z| < z_exit OR z > z_stop.
      - Exit a short when |z| < z_exit OR z < -z_stop.
      - New entries only fill vacant slots (respects top_n cap per side).

    Parameters
    ----------
    residuals_df : (T, N) DataFrame from rolling_pca_residuals().
    window       : Rolling window for z-scoring each residual series.
    z_entry      : Entry threshold.
    z_exit       : Exit threshold.
    z_stop       : Stop-loss threshold.
    top_n        : Maximum simultaneous positions per side.

    Returns
    -------
    (positions_df, z_scores_df)
      positions_df : same shape as residuals_df, values in {-1, 0, +1}.
      z_scores_df  : same shape as residuals_df, rolling z-scores.
    """
    # Global cumulative idiosyncratic return (Avellaneda-Lee s-score approach).
    # The cumsum is the "spread level" and should be mean-reverting when the idiosyncratic
    # component is stationary. The rolling z-score measures deviation from recent equilibrium.
    cumresid  = residuals_df.cumsum()
    roll_mean = cumresid.rolling(window).mean()
    roll_std  = cumresid.rolling(window).std().replace(0, np.nan)
    z_df      = (cumresid - roll_mean) / roll_std

    pos_state = {col: 0 for col in residuals_df.columns}
    pos_rows  = []

    for date, z_row in z_df.iterrows():
        if z_row.isna().all():
            pos_rows.append(dict(pos_state))
            continue

        # 1. Update open positions: exit or stop
        for ticker in list(pos_state):
            z = z_row[ticker]
            p = pos_state[ticker]
            if pd.isna(z) or p == 0:
                continue
            if p == 1 and (abs(z) < z_exit or z > z_stop):
                pos_state[ticker] = 0
            elif p == -1 and (abs(z) < z_exit or z < -z_stop):
                pos_state[ticker] = 0

        # 2. New entries from flat tickers (fill vacant slots)
        flat = [t for t, p in pos_state.items() if p == 0]
        if flat:
            z_flat = z_row[flat].dropna().sort_values()

            n_long  = sum(1 for p in pos_state.values() if p == 1)
            n_short = sum(1 for p in pos_state.values() if p == -1)

            long_slots  = top_n - n_long
            short_slots = top_n - n_short

            if long_slots > 0:
                candidates = z_flat[z_flat < -z_entry]
                for ticker in candidates.index[:long_slots]:
                    pos_state[ticker] = 1

            if short_slots > 0:
                candidates = z_flat[z_flat > z_entry]
                for ticker in candidates.index[-short_slots:]:
                    pos_state[ticker] = -1

        pos_rows.append(dict(pos_state))

    positions_df = pd.DataFrame(pos_rows, index=z_df.index)
    return positions_df, z_df

"""Z-score computation and signal generation for pairs trading."""

import pandas as pd


def compute_zscore(spread: pd.Series, window: int) -> pd.Series:
    """
    Rolling z-score of the spread.

    z = (spread - rolling_mean) / rolling_std

    Values near 0 mean the spread is at its average. Values beyond ±2 are
    the entry triggers — statistically unusual deviations we expect to revert.
    """
    mean = spread.rolling(window).mean()
    std = spread.rolling(window).std()
    zscore = (spread - mean) / std
    zscore.name = "zscore"
    return zscore


def generate_signals(
    zscore: pd.Series,
    z_entry: float = 2.0,
    z_exit: float = 0.5,
    z_stop: float = 3.0,
) -> pd.DataFrame:
    """
    State-machine signal generator from a z-score series.

    Rules:
      - Enter long spread  (long A / short B) when z < -z_entry
      - Enter short spread (short A / long B) when z > +z_entry
      - Exit position when |z| < z_exit  (spread reverted to mean)
      - Stop out when |z| > z_stop  (spread moved further against us)
      - No re-entry while already in a position

    Returns a DataFrame with columns:
      zscore    — the input z-score
      signal    — event label at each bar ('long_spread', 'short_spread',
                  'exit', 'stop', or None)
      position  — running position: 1=long spread, -1=short spread, 0=flat
    """
    signals = []
    position = 0

    for date, z in zscore.items():
        if pd.isna(z):
            signals.append({"date": date, "zscore": z, "signal": None, "position": 0})
            continue

        signal = None

        if position == 0:
            if z < -z_entry:
                signal = "long_spread"
                position = 1
            elif z > z_entry:
                signal = "short_spread"
                position = -1

        elif position == 1:
            if abs(z) < z_exit:
                signal = "exit"
                position = 0
            elif z > z_stop:
                signal = "stop"
                position = 0

        elif position == -1:
            if abs(z) < z_exit:
                signal = "exit"
                position = 0
            elif z < -z_stop:
                signal = "stop"
                position = 0

        signals.append({"date": date, "zscore": z, "signal": signal, "position": position})

    df = pd.DataFrame(signals).set_index("date")
    return df

"""Signal generation for the CTA trend-following strategy."""

import pandas as pd

from src.analytics.cta import combined_ewmac

CTA_UNIVERSE: dict[str, list[str]] = {
    "equities":    ["SPY", "QQQ", "EFA", "EEM", "IWM"],
    "bonds":       ["TLT", "IEF", "SHY", "TIP"],
    "commodities": ["GLD", "SLV", "USO", "DBA"],
    "fx":          ["UUP", "FXE", "FXY"],
}
CTA_UNIVERSE["default"] = (
    CTA_UNIVERSE["equities"]
    + CTA_UNIVERSE["bonds"]
    + CTA_UNIVERSE["commodities"]
    + CTA_UNIVERSE["fx"]
)


def generate_cta_positions(
    prices_df: pd.DataFrame,
    pairs: tuple = ((8, 32), (16, 64), (32, 128), (64, 256)),
    threshold: float = 0.0,
) -> tuple:
    """
    Compute combined EWMAC signals and threshold to binary ±1 positions.

    Parameters
    ----------
    prices_df : (T, N) DataFrame of closing prices.
    pairs     : EWMAC fast/slow pairs to combine.
    threshold : |signal| must exceed this to open a position (0 = always enter).

    Returns
    -------
    (positions_df, signals_df)
      positions_df : {-1, 0, +1} per instrument per bar.
      signals_df   : raw combined EWMAC scores (float, NaN during warm-up).
    """
    signals_map: dict = {}
    positions_map: dict = {}

    for ticker in prices_df.columns:
        sig = combined_ewmac(prices_df[ticker], pairs)
        signals_map[ticker] = sig
        positions_map[ticker] = sig.apply(
            lambda x: 0 if (pd.isna(x) or abs(x) <= threshold)
            else (1 if x > 0 else -1)
        )

    return pd.DataFrame(positions_map, index=prices_df.index), pd.DataFrame(signals_map, index=prices_df.index)

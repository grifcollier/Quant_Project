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


def regime_filter(spy_prices: pd.Series, ma_window: int = 200) -> pd.Series:
    """
    Boolean Series: True when SPY is above its ma_window-day moving average (risk-on).
    False bars suppress all positions regardless of signal strength.
    """
    ma = spy_prices.rolling(ma_window).mean()
    return spy_prices > ma


def generate_cta_positions(
    prices_df: pd.DataFrame,
    pairs: tuple = ((8, 32), (16, 64), (32, 128), (64, 256)),
    threshold: float = 0.0,
    signal_mode: str = "binary",
    spy_prices: pd.Series = None,
    regime_ma: int = 200,
) -> tuple:
    """
    Compute combined EWMAC signals and convert to positions.

    Parameters
    ----------
    prices_df   : (T, N) DataFrame of closing prices.
    pairs       : EWMAC fast/slow pairs to combine.
    threshold   : |signal| must exceed this to open a position (0 = always enter).
    signal_mode : "binary"     → {-1, 0, +1} sign of signal (default)
                  "continuous" → signal scaled to [-1, +1] preserving conviction magnitude
    spy_prices  : Optional SPY closing prices for regime filter. When provided, all
                  equity positions are zeroed on days SPY is below its regime_ma-day MA.
    regime_ma   : Moving-average window for the regime filter (default: 200).

    Returns
    -------
    (positions_df, signals_df)
      positions_df : positions per instrument per bar.
      signals_df   : raw combined EWMAC scores (float, NaN during warm-up).
    """
    import numpy as np

    signals_map: dict = {}
    positions_map: dict = {}

    risk_on = None
    if spy_prices is not None:
        risk_on = regime_filter(spy_prices, ma_window=regime_ma).reindex(prices_df.index).fillna(False)

    for ticker in prices_df.columns:
        sig = combined_ewmac(prices_df[ticker], pairs)
        signals_map[ticker] = sig

        mask_zero = sig.isna() | (sig.abs() <= threshold)
        if signal_mode == "continuous":
            pos = sig.clip(-2, 2) / 2
        else:
            pos = pd.Series(np.sign(sig.fillna(0.0)), index=sig.index)
        pos = pos.where(~mask_zero, 0.0)

        # Regime filter: zero out long equity positions in risk-off regime.
        # Shorts and non-equity instruments are left untouched — they often
        # perform well in downtrends and provide the hedge.
        if risk_on is not None and ticker in ["SPY", "QQQ", "EFA", "EEM", "IWM"]:
            pos = pos.where(risk_on | (pos <= 0), 0.0)

        positions_map[ticker] = pos

    return pd.DataFrame(positions_map, index=prices_df.index), pd.DataFrame(signals_map, index=prices_df.index)

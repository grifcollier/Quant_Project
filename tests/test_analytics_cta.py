"""Smoke tests for CTA analytics functions."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.cta import ewmac, instrument_vol, vol_targeted_weights


def test_ewmac_range(small_prices_df):
    """EWMAC signal should be clipped to [-2, 2]."""
    for col in small_prices_df.columns:
        sig = ewmac(small_prices_df[col], fast=8, slow=32)
        clean = sig.dropna()
        assert (clean >= -2.0 - 1e-9).all() and (clean <= 2.0 + 1e-9).all(), \
            f"EWMAC for {col} has values outside [-2, 2]"


def test_instrument_vol_positive(small_prices_df):
    """Instrument volatility should be non-negative."""
    for col in small_prices_df.columns:
        vol = instrument_vol(small_prices_df[col])
        assert (vol.dropna() >= 0).all(), f"Vol for {col} has negative values"


def test_vol_targeted_weights_zero_positions(small_prices_df):
    """All-zero positions should produce all-zero weights."""
    pos = pd.DataFrame(0.0, index=small_prices_df.index, columns=small_prices_df.columns)
    wt = vol_targeted_weights(pos, small_prices_df, tau=0.20)
    assert (wt == 0.0).all().all(), "Zero positions should produce zero weights"


def test_vol_targeted_weights_shape(small_prices_df):
    """Weights should have same shape as positions."""
    pos = pd.DataFrame(1, index=small_prices_df.index, columns=small_prices_df.columns).astype(float)
    wt = vol_targeted_weights(pos, small_prices_df, tau=0.20)
    assert wt.shape == pos.shape


def test_vol_targeted_weights_cap(small_prices_df):
    """Weight cap should be respected."""
    pos = pd.DataFrame(1, index=small_prices_df.index, columns=small_prices_df.columns).astype(float)
    cap = 0.10
    wt = vol_targeted_weights(pos, small_prices_df, tau=0.20, weight_cap=cap)
    assert (wt.abs() <= cap + 1e-9).all().all(), f"Weights exceed cap of {cap}"


def test_vol_targeted_weights_corr_adjust(small_prices_df):
    """corr_adjust=True should not crash and produce non-zero weights."""
    pos = pd.DataFrame(1, index=small_prices_df.index, columns=small_prices_df.columns).astype(float)
    wt = vol_targeted_weights(pos, small_prices_df, tau=0.20, corr_adjust=True)
    assert wt.shape == pos.shape
    # After warm-up period, some weights should be non-zero
    assert (wt.iloc[100:] != 0).any().any(), "corr_adjust weights should be non-zero after warm-up"

"""Smoke tests for CTA signal generation."""

import numpy as np
import pandas as pd
import pytest

from src.strategies.cta.signals import generate_cta_positions


def test_binary_values(small_prices_df):
    pos, _ = generate_cta_positions(small_prices_df, threshold=0.0, signal_mode="binary")
    valid = pos.stack().dropna()
    assert set(valid.unique()).issubset({-1.0, 0.0, 1.0}), "Binary positions must be in {-1, 0, +1}"


def test_threshold_zeros_all(small_prices_df):
    # EWMAC is clipped to ±2, so threshold=2.0 should zero all positions
    pos, _ = generate_cta_positions(small_prices_df, threshold=2.0, signal_mode="binary")
    assert (pos.fillna(0) == 0).all().all(), "All positions should be zero when threshold >= signal cap"


def test_continuous_range(small_prices_df):
    pos, _ = generate_cta_positions(small_prices_df, threshold=0.0, signal_mode="continuous")
    abs_vals = pos.fillna(0).abs()
    assert (abs_vals <= 1.0 + 1e-9).all().all(), "Continuous positions must be in [-1, +1]"


def test_output_shape(small_prices_df):
    pos, sig = generate_cta_positions(small_prices_df)
    assert pos.shape == small_prices_df.shape
    assert sig.shape == small_prices_df.shape


def test_threshold_reduces_positions(small_prices_df):
    pos_no_thresh, _ = generate_cta_positions(small_prices_df, threshold=0.0)
    pos_with_thresh, _ = generate_cta_positions(small_prices_df, threshold=0.5)
    n_no = (pos_no_thresh != 0).sum().sum()
    n_with = (pos_with_thresh != 0).sum().sum()
    assert n_with <= n_no, "Higher threshold should produce fewer or equal active positions"


def test_continuous_has_more_granularity(small_prices_df):
    pos_bin, _ = generate_cta_positions(small_prices_df, signal_mode="binary")
    pos_con, _ = generate_cta_positions(small_prices_df, signal_mode="continuous")
    unique_bin = len(pos_bin.stack().dropna().unique())
    unique_con = len(pos_con.stack().dropna().unique())
    assert unique_con > unique_bin, "Continuous mode should have more unique position values than binary"

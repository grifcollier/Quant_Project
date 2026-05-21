"""Smoke tests for the portfolio backtest engine."""

import numpy as np
import pandas as pd
import pytest

from src.backtest.portfolio_engine import run_portfolio_backtest


def test_buy_and_hold_grows(small_prices_df):
    """All-long positions with zero cost should produce growing equity on upward-drift prices."""
    pos = pd.DataFrame(1, index=small_prices_df.index, columns=small_prices_df.columns)
    eq, m = run_portfolio_backtest(pos, small_prices_df, capital=10_000, cost_bps=0)
    assert float(eq["equity"].iloc[-1]) > 10_000, "Equity should grow on positive-drift prices"


def test_flat_positions_flat_equity(small_prices_df):
    """All-zero positions should leave equity at starting capital."""
    pos = pd.DataFrame(0, index=small_prices_df.index, columns=small_prices_df.columns)
    eq, m = run_portfolio_backtest(pos, small_prices_df, capital=10_000, cost_bps=0)
    final = float(eq["equity"].iloc[-1])
    assert abs(final - 10_000) < 1.0, f"Zero positions should keep equity flat, got {final}"


def test_costs_reduce_equity(small_prices_df):
    """Higher transaction costs should produce lower final equity when positions change."""
    # Alternate long/flat every 5 bars to generate real turnover
    pos_vals = np.where(
        (np.arange(len(small_prices_df)) // 5) % 2 == 0, 1, 0
    )
    pos = pd.DataFrame(
        np.tile(pos_vals[:, None], (1, small_prices_df.shape[1])),
        index=small_prices_df.index, columns=small_prices_df.columns,
    ).astype(float)
    eq_zero, _ = run_portfolio_backtest(pos, small_prices_df, capital=10_000, cost_bps=0)
    eq_high, _ = run_portfolio_backtest(pos, small_prices_df, capital=10_000, cost_bps=100)
    assert float(eq_high["equity"].iloc[-1]) < float(eq_zero["equity"].iloc[-1]), \
        "Higher costs should produce lower equity when positions turn over"


def test_metrics_shape(small_prices_df):
    """Metrics dict should contain the expected keys."""
    pos = pd.DataFrame(1, index=small_prices_df.index, columns=small_prices_df.columns)
    _, m = run_portfolio_backtest(pos, small_prices_df, capital=10_000)
    required = {"total_return", "cagr", "sharpe", "sortino", "max_drawdown", "calmar"}
    assert required.issubset(set(m.keys())), f"Missing metric keys: {required - set(m.keys())}"


def test_positive_return_positive_sharpe(small_prices_df):
    """A consistently profitable strategy should have positive Sharpe."""
    pos = pd.DataFrame(1, index=small_prices_df.index, columns=small_prices_df.columns)
    _, m = run_portfolio_backtest(pos, small_prices_df, capital=10_000, cost_bps=0)
    assert m["sharpe"] > 0, "Positive-return strategy should have positive Sharpe"


def test_weights_df_used_when_provided(small_prices_df):
    """Custom weights_df should be used instead of equal-weight normalisation."""
    pos = pd.DataFrame(1, index=small_prices_df.index, columns=small_prices_df.columns)
    # All weight in the first instrument
    wt = pd.DataFrame(0.0, index=small_prices_df.index, columns=small_prices_df.columns)
    wt["A"] = 1.0
    eq_wt,  _ = run_portfolio_backtest(pos, small_prices_df, capital=10_000, weights_df=wt)
    eq_eq,  _ = run_portfolio_backtest(pos, small_prices_df, capital=10_000)
    # Results should differ since weight allocation differs
    assert not eq_wt["equity"].equals(eq_eq["equity"]), \
        "Custom weights_df should produce different results from equal-weight"

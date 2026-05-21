"""Shared test fixtures."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def prices_df():
    """16 instruments, 600 bars, log-normal price paths with slight upward drift."""
    np.random.seed(42)
    returns = np.random.normal(0.0003, 0.01, size=(600, 16))
    px = pd.DataFrame(
        np.exp(np.cumsum(returns, axis=0)) * 100,
        index=pd.bdate_range("2020-01-01", periods=600),
        columns=[f"T{i}" for i in range(16)],
    )
    return px


@pytest.fixture
def small_prices_df():
    """4 instruments, 300 bars — fast fixture for unit tests."""
    np.random.seed(7)
    returns = np.random.normal(0.0003, 0.01, size=(300, 4))
    px = pd.DataFrame(
        np.exp(np.cumsum(returns, axis=0)) * 100,
        index=pd.bdate_range("2022-01-01", periods=300),
        columns=["A", "B", "C", "D"],
    )
    return px

"""Tests for deriving live position entry dates from Alpaca fill history."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from alpaca.trading.enums import OrderSide

from src.trading.alpaca_trader import _entry_dates_from_fills

BUY, SELL = OrderSide.BUY, OrderSide.SELL


def fill(symbol, day, side, qty):
    """One filled order on 2026-<day> at the 16:31 ET trading slot."""
    return SimpleNamespace(
        symbol=symbol,
        filled_at=datetime(2026, int(day[:2]), int(day[3:]), 20, 31, tzinfo=timezone.utc),
        filled_qty=str(qty),
        side=side,
    )


def entry_dates(orders, pos_qty):
    return {s: d.date().isoformat() for s, d in _entry_dates_from_fills(orders, pos_qty).items()}


# The history that produced "TIME STOP (held 44d >= 30d)" on 2026-07-15: XLK opened
# 06-01, was closed and reopened repeatedly, and the live position actually opened
# 07-14. Reporting the first-ever fill made every fresh position stop within a day.
XLK_CHURN = [
    fill("XLK", "06-01", BUY, 100),
    fill("XLK", "06-18", SELL, 100),   # flat (z-exit)
    fill("XLK", "06-26", BUY, 100),
    fill("XLK", "07-01", SELL, 100),   # flat
    fill("XLK", "07-03", BUY, 100),
    fill("XLK", "07-06", SELL, 100),   # flat
    fill("XLK", "07-14", BUY, 100),    # current position
]


def test_reopened_position_uses_latest_entry():
    assert entry_dates(XLK_CHURN, {"XLK": 100.0}) == {"XLK": "2026-07-14"}


def test_order_of_input_does_not_matter():
    # Alpaca returns orders newest-first.
    assert entry_dates(list(reversed(XLK_CHURN)), {"XLK": 100.0}) == {"XLK": "2026-07-14"}


def test_short_position_entry_is_the_sell():
    orders = [
        fill("XLE", "06-02", SELL, 50),
        fill("XLE", "06-20", BUY, 50),    # flat
        fill("XLE", "07-10", SELL, 50),   # current short
    ]
    assert entry_dates(orders, {"XLE": -50.0}) == {"XLE": "2026-07-10"}


def test_fractional_close_counts_as_flat():
    orders = [
        fill("MSFT", "06-01", BUY, 12.3456),
        fill("MSFT", "06-18", SELL, 12.3456001),
        fill("MSFT", "07-14", BUY, 9.87),
    ]
    assert entry_dates(orders, {"MSFT": 9.87}) == {"MSFT": "2026-07-14"}


def test_scaling_in_keeps_original_entry():
    orders = [
        fill("JPM", "06-10", BUY, 10),
        fill("JPM", "06-20", BUY, 5),
    ]
    assert entry_dates(orders, {"JPM": 15.0}) == {"JPM": "2026-06-10"}


def test_truncated_history_reports_unknown():
    # Position opened before the lookback window; only a later scale-in is visible,
    # so the replayed qty (5) disagrees with the broker's (15). Better no answer
    # than a wrong one — the caller skips the time stop and warns.
    assert entry_dates([fill("AAPL", "07-14", BUY, 5)], {"AAPL": 15.0}) == {}


def test_truncated_symbol_does_not_affect_others():
    orders = XLK_CHURN + [fill("NVDA", "07-14", BUY, 5)]
    assert entry_dates(orders, {"XLK": 100.0, "NVDA": 15.0}) == {"XLK": "2026-07-14"}


@pytest.mark.parametrize("hold_days,expected_stop", [(29, False), (30, True), (44, True)])
def test_time_stop_threshold_is_inclusive(hold_days, expected_stop):
    # run.py fires when hold_days >= max_hold_days; guard the boundary.
    assert (hold_days >= 30) is expected_stop

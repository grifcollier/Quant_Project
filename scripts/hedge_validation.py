"""
Beta-hedge overlay validation.

Phase 1 — membership churn:
    Compare hedge-basket membership stability across three regimes:
      (a) quarterly-only baseline  : top-5 by weight from each N-PORT filing
      (b) daily, NO hysteresis     : re-rank top-5 by shares*price every day
      (c) daily + hysteresis       : the shipped rule (x_pp=0.3, n_days=3)
    Confirms hysteresis (c) does not introduce materially more churn than the
    quarterly baseline (a), while (b) shows the raw daily flip-flop rate.

Phase 5 — hedged vs unhedged (added later in this script).

Usage
-----
    python scripts/hedge_validation.py            # XLK and XLI
    python scripts/hedge_validation.py XLK
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data.fetcher import fetch_prices_bulk
from src.data.edgar import build_constituent_history
from src.strategies.basket.hedge import hedge_membership

PERIOD = "5y"
HOLD_N = 5
POOL_N = 10
X_PP = 0.3
N_DAYS = 3

DEFAULT_ETFS = ["XLK", "XLI"]


def _count_changes(members_by_day: pd.Series) -> tuple[int, int]:
    """Return (n_change_days, n_distinct_sets) for a day-indexed Series of lists."""
    prev = None
    changes = 0
    distinct = 0
    for m in members_by_day:
        s = frozenset(m)
        if prev is None:
            distinct = 1
        elif s != prev:
            changes += 1
            distinct += 1
        prev = s
    return changes, distinct


def _quarterly_changes(hist: pd.DataFrame, hold_n: int) -> int:
    prev = None
    changes = 0
    for _, row in hist.iterrows():
        s = frozenset(list(row["constituents"])[:hold_n])
        if prev is not None and s != prev:
            changes += 1
        prev = s
    return changes


def validate_phase1(etf: str) -> None:
    print(f"\n{'='*70}\n{etf} — Phase 1 membership churn\n{'='*70}")
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=5)

    hist = build_constituent_history(
        etf, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
        top_n=POOL_N, include_shares=True,
    )
    if hist.empty:
        print("  no history")
        return

    pool = sorted({t for row in hist["constituents"] for t in row})
    prices = fetch_prices_bulk(pool, period=PERIOD)
    px = pd.DataFrame({t: prices[t] for t in pool if t in prices}).dropna(how="all")

    # (a) quarterly baseline
    q_changes = _quarterly_changes(hist, HOLD_N)
    n_filings = len(hist)

    # (b) daily, no hysteresis
    m_raw = hedge_membership(hist, px, hold_n=HOLD_N, pool_n=POOL_N, x_pp=0.0, n_days=1)
    raw_changes, raw_distinct = _count_changes(m_raw["members"])

    # (c) daily + hysteresis (shipped)
    m_hys = hedge_membership(hist, px, hold_n=HOLD_N, pool_n=POOL_N, x_pp=X_PP, n_days=N_DAYS)
    hys_changes, hys_distinct = _count_changes(m_hys["members"])

    n_days = len(m_hys)
    print(f"  trading days covered: {n_days}   quarterly filings: {n_filings}")
    print(f"  (a) quarterly baseline : {q_changes:3d} changes over {n_filings-1} transitions "
          f"({q_changes/(n_filings-1):.0%})")
    print(f"  (b) daily, NO hysteresis: {raw_changes:3d} change-days  "
          f"({raw_changes/n_days:.1%} of days)   {raw_distinct} distinct sets")
    print(f"  (c) daily + hysteresis  : {hys_changes:3d} change-days  "
          f"({hys_changes/n_days:.1%} of days)   {hys_distinct} distinct sets")
    print(f"  hysteresis cut raw daily churn by "
          f"{(1 - hys_changes/max(raw_changes,1)):.0%}; "
          f"vs quarterly baseline it is {'<=' if hys_changes <= q_changes else '>'} "
          f"({hys_changes} vs {q_changes} changes)")


if __name__ == "__main__":
    etfs = [a.upper() for a in sys.argv[1:]] or DEFAULT_ETFS
    for e in etfs:
        validate_phase1(e)

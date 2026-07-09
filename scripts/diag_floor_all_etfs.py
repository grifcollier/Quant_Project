"""
Floor-at-zero diagnostic across all five trading ETFs.

Reports per-ETF: flooring frequency per stock, surviving-stock distribution,
and worst-case concentration. Uses approximate current top-5 constituents
(same stocks the live trader would resolve from EDGAR).

Usage:
    python scripts/diag_floor_all_etfs.py
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data.fetcher import fetch_price, fetch_prices_bulk

BASKETS = {
    "XLF": ["JPM", "BAC", "WFC", "GS",  "MS"],
    "XLV": ["UNH", "LLY", "JNJ", "ABBV","MRK"],
    "XLI": ["GE",  "RTX", "CAT", "HON", "UNP"],
    "XLK": ["AAPL","MSFT","NVDA","AVGO","ORCL"],
    "XLE": ["XOM", "CVX", "COP", "EOG", "SLB"],
}

PERIOD       = "2y"
WINDOW       = 60
MIN_SURVIVORS = 3

print(f"Period: {PERIOD}  |  Window: {WINDOW}d  |  Min survivors: {MIN_SURVIVORS}\n")

summary_rows = []

for etf, stocks in BASKETS.items():
    print(f"Fetching {etf} + {stocks}...")
    try:
        etf_px = fetch_price(etf, period=PERIOD)
        prices = fetch_prices_bulk(stocks, period=PERIOD)
    except Exception as e:
        print(f"  ERROR fetching {etf}: {e}")
        continue

    avail = [s for s in stocks if s in prices]
    if len(avail) < 2:
        print(f"  Skipping {etf} — fewer than 2 stocks fetched.")
        continue

    cdf = pd.DataFrame({s: prices[s] for s in avail}).dropna()
    ea  = etf_px.reindex(cdf.index).dropna()
    cdf = cdf.reindex(ea.index)

    y_all = np.log(ea.values).astype(float)
    X_all = np.log(cdf.values).astype(float)
    n     = len(ea)

    all_coefs   = []
    dates       = []
    for t in range(WINDOW, n):
        X_aug = np.column_stack([np.ones(WINDOW), X_all[t - WINDOW : t]])
        coeffs, _, _, _ = np.linalg.lstsq(X_aug, y_all[t - WINDOW : t], rcond=None)
        all_coefs.append(coeffs[1:])
        dates.append(ea.index[t])

    coef_mat  = np.array(all_coefs)
    floored   = np.maximum(coef_mat, 0.0)
    n_surv    = (floored > 0).sum(axis=1)
    coef_sums = floored.sum(axis=1)
    n_bars    = len(coef_mat)

    # Worst-case concentration
    with np.errstate(divide="ignore", invalid="ignore"):
        max_wt = np.where(coef_sums > 0, floored.max(axis=1) / coef_sums, np.nan)
    valid_wt = max_wt[~np.isnan(max_wt)]

    # Bars that would block new entries
    blocked_bars = int((n_surv < MIN_SURVIVORS).sum())

    print(f"\n  {etf}  ({n_bars} bars)")
    print(f"  {'Stock':<6}  {'Floored bars':>12}  {'Pct':>6}")
    for i, s in enumerate(avail):
        nf = int((coef_mat[:, i] <= 0).sum())
        print(f"  {s:<6}  {nf:>12d}  {100*nf/n_bars:>5.1f}%")

    print(f"  Surviving-stock distribution:")
    for k in range(0, len(avail) + 1):
        cnt = int((n_surv == k).sum())
        if cnt > 0:
            flag = "  <-- ENTRY BLOCKED" if k < MIN_SURVIVORS else ""
            print(f"    {k} stocks: {cnt:4d} bars ({100*cnt/n_bars:.1f}%){flag}")

    print(f"  Worst-case single-stock concentration: {valid_wt.max():.1%}"
          f"  |  p95: {np.percentile(valid_wt, 95):.1%}"
          f"  |  mean: {valid_wt.mean():.1%}")
    print(f"  Entry-blocked bars: {blocked_bars} / {n_bars} ({100*blocked_bars/n_bars:.1f}%)")

    summary_rows.append({
        "ETF":           etf,
        "Bars":          n_bars,
        "Blocked bars":  blocked_bars,
        "Blocked %":     round(100 * blocked_bars / n_bars, 1),
        "Worst conc.":   f"{valid_wt.max():.1%}",
        "p95 conc.":     f"{np.percentile(valid_wt, 95):.1%}",
    })

print(f"\n{'='*60}")
print(f"Summary")
print(f"{'='*60}")
df = pd.DataFrame(summary_rows)
print(df.to_string(index=False))

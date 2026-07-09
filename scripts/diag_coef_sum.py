"""
Diagnostic: check whether OLS basket coefficients sum to ~1 and intercept ~0.

Usage:
    python scripts/diag_coef_sum.py
"""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data.fetcher import fetch_price, fetch_prices_bulk

ETF     = "XLK"
STOCKS  = ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL"]
PERIOD  = "2y"
WINDOW  = 60

print(f"Fetching {ETF} + {STOCKS} ({PERIOD})...")
etf_px = fetch_price(ETF, period=PERIOD)
px     = fetch_prices_bulk(STOCKS, period=PERIOD)
cdf    = pd.DataFrame(px).dropna()
ea     = etf_px.reindex(cdf.index).dropna()
cdf    = cdf.reindex(ea.index)

y_all = np.log(ea.values).astype(float)
X_all = np.log(cdf.values).astype(float)
n     = len(ea)

coef_sums   = []
intercepts  = []
dates       = []

for t in range(WINDOW, n):
    y_train = y_all[t - WINDOW : t]
    X_train = X_all[t - WINDOW : t]
    X_aug   = np.column_stack([np.ones(WINDOW), X_train])
    coeffs, _, _, _ = np.linalg.lstsq(X_aug, y_train, rcond=None)
    intercepts.append(float(coeffs[0]))
    coef_sums.append(float(coeffs[1:].sum()))
    dates.append(ea.index[t])

cs = pd.Series(coef_sums, index=dates, name="coef_sum")
ic = pd.Series(intercepts, index=dates, name="intercept")

print(f"\n{'='*50}")
print(f"ETF: {ETF}  |  Stocks: {', '.join(STOCKS)}")
print(f"Window: {WINDOW}d  |  Bars: {len(cs)}")
print(f"{'='*50}")
print(f"\nSum(b_i) (should be ~1.0):")
print(f"  mean  = {cs.mean():.4f}")
print(f"  std   = {cs.std():.4f}")
print(f"  min   = {cs.min():.4f}")
print(f"  max   = {cs.max():.4f}")
print(f"  p5    = {cs.quantile(0.05):.4f}")
print(f"  p95   = {cs.quantile(0.95):.4f}")

print(f"\nIntercept a (should be ~0.0):")
print(f"  mean  = {ic.mean():.4f}")
print(f"  std   = {ic.std():.4f}")
print(f"  min   = {ic.min():.4f}")
print(f"  max   = {ic.max():.4f}")
print(f"  p5    = {ic.quantile(0.05):.4f}")
print(f"  p95   = {ic.quantile(0.95):.4f}")

print(f"\nIndividual coef means across all windows:")
all_coefs = []
for t in range(WINDOW, n):
    y_train = y_all[t - WINDOW : t]
    X_train = X_all[t - WINDOW : t]
    X_aug   = np.column_stack([np.ones(WINDOW), X_train])
    coeffs, _, _, _ = np.linalg.lstsq(X_aug, y_train, rcond=None)
    all_coefs.append(coeffs[1:])

coef_mat   = np.array(all_coefs)          # shape (n_bars, n_stocks)
n_bars     = len(coef_mat)
tickers    = list(cdf.columns)

for i, ticker in enumerate(tickers):
    print(f"  {ticker:6s}  mean={coef_mat[:,i].mean():.4f}  "
          f"std={coef_mat[:,i].std():.4f}  "
          f"min={coef_mat[:,i].min():.4f}  "
          f"max={coef_mat[:,i].max():.4f}")

# --- Floor-at-zero analysis ---------------------------------------------------
floored     = np.maximum(coef_mat, 0.0)                   # (n_bars, n_stocks)
n_surviving = (floored > 0).sum(axis=1)                   # stocks surviving per bar
coef_sums_f = floored.sum(axis=1)                         # sum of floored coefs per bar

print(f"\n{'='*50}")
print(f"Floor-at-zero concentration analysis")
print(f"{'='*50}")

# 1. Per-stock flooring frequency
print(f"\nHow often each stock is floored (coef <= 0):")
for i, ticker in enumerate(tickers):
    n_floored = (coef_mat[:, i] <= 0).sum()
    print(f"  {ticker:6s}  {n_floored:4d} / {n_bars} bars  ({100*n_floored/n_bars:.1f}%)")

# 2. Surviving stock count distribution
print(f"\nDistribution of surviving stocks per bar:")
for k in range(0, len(tickers) + 1):
    count = (n_surviving == k).sum()
    if count > 0:
        print(f"  {k} stocks survive: {count:4d} bars ({100*count/n_bars:.1f}%)")

# 3. Worst-case concentration
print(f"\nWorst-case concentration (max weight any single stock receives):")
with np.errstate(divide='ignore', invalid='ignore'):
    max_weight = np.where(coef_sums_f > 0,
                          floored.max(axis=1) / coef_sums_f,
                          np.nan)

valid = max_weight[~np.isnan(max_weight)]
print(f"  mean max-weight : {valid.mean():.1%}")
print(f"  p95 max-weight  : {np.percentile(valid, 95):.1%}")
print(f"  worst bar       : {valid.max():.1%}")

# Show the actual bar where concentration is worst
worst_idx = np.nanargmax(max_weight)
worst_date = dates[worst_idx]
worst_coefs = coef_mat[worst_idx]
worst_floored = floored[worst_idx]
worst_sum = coef_sums_f[worst_idx]
print(f"\n  Worst bar: {worst_date.date()}")
for i, ticker in enumerate(tickers):
    raw  = worst_coefs[i]
    floored_w = worst_floored[i]
    alloc = floored_w / worst_sum if worst_sum > 0 else 0.0
    flag = " <-- sole survivor" if alloc == 1.0 else (f" ({alloc:.0%} of half_notional)" if alloc > 0.5 else "")
    print(f"    {ticker:6s}  raw={raw:+.4f}  floored={floored_w:.4f}  alloc={alloc:.1%}{flag}")

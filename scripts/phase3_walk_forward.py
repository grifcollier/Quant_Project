"""
Phase 3 walk-forward validation: OLS baseline vs. dynamic ridge (threshold=20).

Design
------
- Full period : 5y (period="5y")
- Train       : first 2.5y -- observe condition-number distribution, confirm
                threshold=20 captures the expected fraction of bars
- Test        : last 2.5y  -- 5 walk-forward folds of ~126 bars (~6 months)
- Ridge       : threshold=20, alpha grid {0.1, 1.0, 10.0}, fixed pre-test
- Constituents: EDGAR N-PORT dynamic segments (same as live strategy)
- Stationarity gate: flag any fold where OLS spread is stationary (ADF p<0.10)
  but ridge spread is NOT -- that would mean ridge broke the tradeable signal

XLK supplement
--------------
The V/MA stress segment (2022-02-25 - 2023-05-29, mean cond=58.7) falls
entirely inside the train window. A supplemental full-5y fold analysis
tags each fold as 'stress' or 'normal' to show regime-level behaviour.

Usage
-----
    python scripts/phase3_walk_forward.py
"""
import sys, math
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data.fetcher     import fetch_price, fetch_prices_bulk
from src.data.edgar       import get_constituent_segments
from src.analytics.basket import rolling_basket_spread
from src.analytics.stationarity import adf_test, compute_half_life, stationarity_gate
from src.strategies.basket.signals  import generate_basket_signals
from src.strategies.basket.backtest import run_basket_backtest

# -- Configuration -------------------------------------------------------------
PERIOD          = "5y"
WINDOW          = 60
RIDGE_THRESHOLD = 20.0
FOLD_BARS       = 126          # ~6 months per fold
CAPITAL         = 20_000.0
Z_ENTRY         = 1.5
Z_EXIT          = 0.5
Z_STOP          = 3.0
COST_BPS        = 5.0
TOP_N           = 5
ADF_SIG         = 0.10         # stationarity significance level

XLK_STRESS_START = pd.Timestamp("2022-02-25")
XLK_STRESS_END   = pd.Timestamp("2023-05-29")

ETFS = ["XLK", "XLF", "XLV", "XLI", "XLE"]
FALLBACK_BASKETS = {
    "XLK": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL"],
    "XLF": ["JPM",  "BAC",  "WFC",  "GS",   "MS"  ],
    "XLV": ["UNH",  "LLY",  "JNJ",  "ABBV", "MRK" ],
    "XLI": ["GE",   "RTX",  "CAT",  "HON",  "UNP" ],
    "XLE": ["XOM",  "CVX",  "COP",  "EOG",  "SLB" ],
}

# -- Helpers -------------------------------------------------------------------
def _nan(v):
    return float("nan") if (v is None or (isinstance(v, float) and math.isnan(v))) else v

def _fmt(v, fmt=".2f"):
    return "  n/a" if (v is None or (isinstance(v, float) and math.isnan(v))) else format(v, fmt)

def _stitch(pieces):
    if not pieces:
        return pd.Series(dtype=float)
    s = pd.concat(pieces).sort_index()
    return s[~s.index.duplicated(keep="first")]

def _build_spreads(etf_prices, segs, prices):
    """
    Per-segment OLS and ridge spreads. Returns four stitched series:
    ols_spread, ridge_spread, cond_series, cap_series
    """
    ols_p, rdg_p, cnd_p, cap_p = [], [], [], []
    for s_start, s_end, stx in segs:
        avail = [s for s in stx if s in prices]
        if len(avail) < 2:
            continue
        cdf = pd.DataFrame({s: prices[s] for s in avail}).dropna()
        ea  = etf_prices.reindex(cdf.index).dropna()
        cdf = cdf.reindex(ea.index)
        if len(cdf) < WINDOW + 5:
            continue

        ols_full = rolling_basket_spread(ea, cdf, window=WINDOW)
        rdg_full, cnd_full, cap_full = rolling_basket_spread(
            ea, cdf, window=WINDOW,
            ridge_threshold=RIDGE_THRESHOLD, return_diagnostics=True,
        )
        ols_p.append(ols_full.loc[s_start:s_end])
        rdg_p.append(rdg_full.loc[s_start:s_end])
        cnd_p.append(cnd_full.loc[s_start:s_end])
        cap_p.append(cap_full.loc[s_start:s_end])

    return _stitch(ols_p), _stitch(rdg_p), _stitch(cnd_p), _stitch(cap_p)

def _fold_metrics(signals, spread, cond_series, cap_series, fs, fe, is_ridge):
    sig_f  = signals.loc[fs:fe]
    spd_f  = spread.loc[fs:fe]
    t, eq, m = run_basket_backtest(
        sig_f, spd_f, capital=CAPITAL, cost_bps=COST_BPS,
    )
    spd_v  = spd_f.dropna()
    adf_r  = adf_test(spd_v)       if len(spd_v) > 10 else {"p_value": float("nan")}
    hl_v   = compute_half_life(spd_v) if len(spd_v) > 10 else float("nan")

    cnd_f  = cond_series.loc[fs:fe].dropna()
    mean_c = float(cnd_f.mean())            if not cnd_f.empty else float("nan")
    pct_r  = float((cnd_f > RIDGE_THRESHOLD).mean()) if not cnd_f.empty else float("nan")

    cap_f  = cap_series.loc[fs:fe]
    pct_c  = float(cap_f.mean())            if len(cap_f) > 0 else float("nan")

    return {
        "n_trades":    m.get("n_trades",    0),
        "sharpe":      _nan(m.get("sharpe")),
        "max_dd":      _nan(m.get("max_drawdown")),
        "total_ret":   _nan(m.get("total_return")),
        "win_rate":    _nan(m.get("win_rate")),
        "adf_pval":    adf_r["p_value"],
        "half_life":   hl_v,
        "mean_cond":   mean_c,
        "pct_ridge":   pct_r,
        "pct_cap_hit": pct_c,
    }

def _hdr(label):
    print(f"\n{'='*78}")
    print(f"  {label}")
    print(f"{'='*78}")

def _print_fold_table(fold_rows, stat_alerts):
    W = 9
    hdr = (f"  {'Fold':<5} {'Period':<24} {'Trades':>6} {'Sharpe':>{W}} "
           f"{'MaxDD':>{W}} {'Ret':>{W}} {'ADF_p':>{W}} {'HL':>{W}} "
           f"{'MnCond':>{W}} {'%Ridge':>{W}} {'%Cap':>{W}}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in fold_rows:
        alert = " *** STAT ALERT" if r.get("stat_alert") else ""
        print(
            f"  {r['fold']:<5} "
            f"{str(r['start'].date())+' - '+str(r['end'].date()):<24} "
            f"{r['n_trades']:>6} "
            f"{_fmt(r['sharpe']):>9} "
            f"{_fmt(r['max_dd'], '.1%'):>9} "
            f"{_fmt(r['total_ret'], '.1%'):>9} "
            f"{_fmt(r['adf_pval'], '.3f'):>9} "
            f"{_fmt(r['half_life'], '.0f'):>9} "
            f"{_fmt(r['mean_cond'], '.1f'):>9} "
            f"{_fmt(r['pct_ridge'], '.0%'):>9} "
            f"{_fmt(r['pct_cap_hit'], '.1%'):>9}"
            f"{alert}"
        )

def _overall(fold_rows, label):
    def avg(k): return float(np.nanmean([r[k] for r in fold_rows]))
    def tot(k): return int(sum(r[k] for r in fold_rows))
    print(f"  {label}  trades={tot('n_trades')}  "
          f"sharpe={avg('sharpe'):.2f}  maxdd={avg('max_dd'):.1%}  "
          f"ret={avg('total_ret'):.1%}  adf_p={avg('adf_pval'):.3f}  "
          f"hl={avg('half_life'):.0f}d  "
          f"pct_ridge={avg('pct_ridge'):.0%}  pct_cap={avg('pct_cap_hit'):.1%}")

# -- Main loop -----------------------------------------------------------------
full_end   = pd.Timestamp.today().normalize()
full_start = full_end - pd.DateOffset(years=5)
train_end  = full_start + pd.DateOffset(months=30)

print(f"\nPhase 3 Walk-Forward Validation")
print(f"Period: {full_start.date()} -> {full_end.date()}")
print(f"Train:  {full_start.date()} -> {train_end.date()}  (first 2.5y)")
print(f"Test:   {train_end.date()} -> {full_end.date()}  (last 2.5y, {FOLD_BARS}-bar folds)")
print(f"Threshold={RIDGE_THRESHOLD}  grid={{0.1, 1.0, 10.0}}  window={WINDOW}  Z={Z_ENTRY}/{Z_EXIT}/{Z_STOP}")

xlk_full_data = None   # saved for supplemental regime-split analysis

for etf in ETFS:
    _hdr(etf)

    # 1. EDGAR segments
    print(f"  Fetching EDGAR segments...")
    try:
        segs = get_constituent_segments(
            etf, full_start, full_end, top_n=TOP_N,
            fallback_stocks=FALLBACK_BASKETS[etf],
        )
    except Exception as e:
        print(f"  EDGAR failed: {e} -- using fallback.")
        segs = [(full_start, full_end, FALLBACK_BASKETS[etf])]
    segs = [(ss, se, [s.replace("/", "-") for s in stx]) for ss, se, stx in segs]
    print(f"  {len(segs)} segment(s)")

    # 2. Fetch prices
    all_tickers = sorted({s for _, _, stx in segs for s in stx})
    prices = fetch_prices_bulk(all_tickers, period=PERIOD)
    etf_px = fetch_price(etf, period=PERIOD)

    # 3. Build stitched spread series
    print(f"  Computing per-segment OLS + ridge spreads...")
    ols_spread, ridge_spread, cond_series, cap_series = _build_spreads(etf_px, segs, prices)

    if ols_spread.empty:
        print(f"  No spread data. Skipping.")
        continue

    # 4. Train-period condition number summary
    train_cond = cond_series.loc[:train_end].dropna()
    if not train_cond.empty:
        pct_above = (train_cond > RIDGE_THRESHOLD).mean()
        print(f"\n  Train stats (cond num, {full_start.date()} -> {train_end.date()}):")
        print(f"    mean={train_cond.mean():.1f}  p50={train_cond.median():.1f}  "
              f"p95={train_cond.quantile(.95):.1f}  max={train_cond.max():.1f}  "
              f"bars>{RIDGE_THRESHOLD:.0f}: {pct_above:.1%}")
        print(f"    Threshold calibration: {'OK -- threshold captures expected regime' if pct_above > 0.01 else 'LOW -- threshold rarely activated in train'}")

    # 5. Generate signals
    ols_sigs, _   = generate_basket_signals(
        ols_spread,   window=WINDOW, z_entry=Z_ENTRY, z_exit=Z_EXIT, z_stop=Z_STOP)
    ridge_sigs, _ = generate_basket_signals(
        ridge_spread, window=WINDOW, z_entry=Z_ENTRY, z_exit=Z_EXIT, z_stop=Z_STOP)

    # 6. Test-period walk-forward
    test_mask = ols_sigs.index >= train_end
    test_idx  = ols_sigs.index[test_mask]
    T         = len(test_idx)
    n_folds   = max(1, T // FOLD_BARS)

    print(f"\n  Test walk-forward: {n_folds} fold(s) x {FOLD_BARS} bars")

    ols_folds, rdg_folds = [], []
    stat_alerts = []

    for i in range(n_folds):
        start_i = T - (n_folds - i) * FOLD_BARS
        end_i   = min(T - (n_folds - i - 1) * FOLD_BARS, T) - 1
        if start_i < 0:
            start_i = 0
        fs = test_idx[start_i]
        fe = test_idx[end_i]

        om = _fold_metrics(ols_sigs,   ols_spread,   cond_series, cap_series, fs, fe, False)
        rm = _fold_metrics(ridge_sigs, ridge_spread, cond_series, cap_series, fs, fe, True)

        gate = stationarity_gate(ols_spread.loc[fs:fe], ridge_spread.loc[fs:fe],
                                 significance=ADF_SIG)
        stat_alert = gate["alert"]
        if stat_alert:
            stat_alerts.append((i + 1, fs, fe))

        fold_label = i + 1
        ols_folds.append({"fold": fold_label, "start": fs, "end": fe, **om, "stat_alert": False})
        rdg_folds.append({"fold": fold_label, "start": fs, "end": fe, **rm, "stat_alert": stat_alert})

    print(f"\n  {'-- BASELINE (OLS) --':-<60}")
    _print_fold_table(ols_folds, stat_alerts)
    _overall(ols_folds, "Overall OLS:")

    print(f"\n  {'-- RIDGE (threshold=20) --':-<60}")
    _print_fold_table(rdg_folds, stat_alerts)
    _overall(rdg_folds, "Overall RDG:")

    if stat_alerts:
        print(f"\n  *** STATIONARITY ALERT -- {len(stat_alerts)} fold(s) where OLS spread stationary "
              f"but ridge spread is NOT (ADF p >= {ADF_SIG}):")
        for fn, fs, fe in stat_alerts:
            print(f"      Fold {fn}: {fs.date()} - {fe.date()}")
    else:
        print(f"\n  Stationarity gate: CLEAR -- no fold where ridge broke spread stationarity")

    # Save XLK data for regime-split supplement
    if etf == "XLK":
        xlk_full_data = (etf_px, segs, prices, ols_spread, ridge_spread,
                         cond_series, cap_series, ols_sigs, ridge_sigs)

# -- XLK supplemental: full-5y regime split -----------------------------------
if xlk_full_data is not None:
    _hdr("XLK -- Supplemental Full-5y Regime Split")
    etf_px, segs, prices, ols_spread, ridge_spread, cond_series, cap_series, ols_sigs, ridge_sigs = xlk_full_data

    print(f"  Stress window: {XLK_STRESS_START.date()} - {XLK_STRESS_END.date()} "
          f"(AAPL/MSFT/NVDA/V/MA, mean cond~58.7)")
    print(f"  Note: stress window falls entirely in the TRAIN period.")
    print(f"  Full-5y folds (chronological, {FOLD_BARS} bars each) allow baseline vs ridge comparison")
    print(f"  across both stress-era and non-stress-era bars, regardless of train/test boundary.\n")

    full_idx = ols_sigs.index
    T_full   = len(full_idx)
    # Start from first full-window bar
    n_full_folds = max(1, (T_full - WINDOW) // FOLD_BARS)
    first_bar    = WINDOW

    print(f"  {n_full_folds} chronological fold(s) across full 5y period:")

    ols_rows, rdg_rows = [], []
    for i in range(n_full_folds):
        start_i = first_bar + i * FOLD_BARS
        end_i   = min(start_i + FOLD_BARS - 1, T_full - 1)
        if start_i >= T_full:
            break
        fs = full_idx[start_i]
        fe = full_idx[end_i]

        overlaps_stress = (fs <= XLK_STRESS_END) and (fe >= XLK_STRESS_START)
        regime = "STRESS" if overlaps_stress else "normal"

        om = _fold_metrics(ols_sigs,   ols_spread,   cond_series, cap_series, fs, fe, False)
        rm = _fold_metrics(ridge_sigs, ridge_spread, cond_series, cap_series, fs, fe, True)
        gate = stationarity_gate(ols_spread.loc[fs:fe], ridge_spread.loc[fs:fe],
                                 significance=ADF_SIG)
        stat_alert = gate["alert"]

        ols_rows.append({"fold": i+1, "start": fs, "end": fe, "regime": regime, **om, "stat_alert": False})
        rdg_rows.append({"fold": i+1, "start": fs, "end": fe, "regime": regime, **rm, "stat_alert": stat_alert})

    # Print combined table with regime tag
    W = 9
    hdr = (f"  {'F':<2} {'Period':<24} {'Regime':<8} "
           f"{'Trades':>6} {'Sharpe':>{W}} {'MaxDD':>{W}} {'ADF_p':>{W}} "
           f"{'MnCond':>{W}} {'%Ridge':>{W}} {'%Cap':>{W}}")
    print(f"\n  {'-- BASELINE (OLS) --':-<60}")
    print(hdr); print("  " + "-"*(len(hdr)-2))
    for r in ols_rows:
        print(f"  {r['fold']:<2} "
              f"{str(r['start'].date())+' - '+str(r['end'].date()):<24} "
              f"{r['regime']:<8} "
              f"{r['n_trades']:>6} "
              f"{_fmt(r['sharpe']):>9} "
              f"{_fmt(r['max_dd'], '.1%'):>9} "
              f"{_fmt(r['adf_pval'], '.3f'):>9} "
              f"{_fmt(r['mean_cond'], '.1f'):>9} "
              f"{_fmt(r['pct_ridge'], '.0%'):>9} "
              f"{_fmt(r['pct_cap_hit'], '.1%'):>9}")

    print(f"\n  {'-- RIDGE (threshold=20) --':-<60}")
    print(hdr); print("  " + "-"*(len(hdr)-2))
    for r in rdg_rows:
        alert = " *** STAT ALERT" if r.get("stat_alert") else ""
        print(f"  {r['fold']:<2} "
              f"{str(r['start'].date())+' - '+str(r['end'].date()):<24} "
              f"{r['regime']:<8} "
              f"{r['n_trades']:>6} "
              f"{_fmt(r['sharpe']):>9} "
              f"{_fmt(r['max_dd'], '.1%'):>9} "
              f"{_fmt(r['adf_pval'], '.3f'):>9} "
              f"{_fmt(r['mean_cond'], '.1f'):>9} "
              f"{_fmt(r['pct_ridge'], '.0%'):>9} "
              f"{_fmt(r['pct_cap_hit'], '.1%'):>9}{alert}")

    # Summary by regime
    for label, rows in [("STRESS", [r for r in rdg_rows if r["regime"] == "STRESS"]),
                         ("normal", [r for r in rdg_rows if r["regime"] == "normal"])]:
        if not rows:
            continue
        ols_r = [r for r in ols_rows if r["regime"] == label]
        def avg(rs, k): return float(np.nanmean([r[k] for r in rs]))
        print(f"\n  Regime={label} ({len(rows)} fold(s)):")
        print(f"    OLS:   sharpe={avg(ols_r,'sharpe'):.2f}  maxdd={avg(ols_r,'max_dd'):.1%}  "
              f"adf_p={avg(ols_r,'adf_pval'):.3f}  mean_cond={avg(ols_r,'mean_cond'):.1f}")
        print(f"    Ridge: sharpe={avg(rows,'sharpe'):.2f}  maxdd={avg(rows,'max_dd'):.1%}  "
              f"adf_p={avg(rows,'adf_pval'):.3f}  pct_ridge={avg(rows,'pct_ridge'):.0%}  "
              f"pct_cap={avg(rows,'pct_cap_hit'):.1%}")

print(f"\n{'='*78}")
print(f"Phase 3 complete.")
print(f"{'='*78}\n")

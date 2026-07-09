"""
Diagnostic: impact of floor-at-zero + minimum-3-survivors on historical trades.

Runs the basket backtest on XLK, then tags each trade's entry date with the
number of stocks that survive the OLS coefficient floor on that day.
Compares metrics between blocked (< 3 survivors) and non-blocked trades.

Usage:
    python scripts/diag_floor_impact.py
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data.fetcher import fetch_price, fetch_prices_bulk
from src.analytics.basket import rolling_basket_spread
from src.strategies.basket.signals import generate_basket_signals
from src.strategies.basket.backtest import run_basket_backtest

BASKETS = {
    "XLF": ["JPM", "BAC", "WFC", "GS",   "MS"],
    "XLV": ["UNH", "LLY", "JNJ", "ABBV", "MRK"],
    "XLI": ["GE",  "RTX", "CAT", "HON",  "UNP"],
    "XLK": ["AAPL","MSFT","NVDA","AVGO", "ORCL"],
    "XLE": ["XOM", "CVX", "COP", "EOG",  "SLB"],
}

ETF     = sys.argv[1].upper() if len(sys.argv) > 1 else "XLK"
STOCKS  = BASKETS[ETF]
PERIOD  = "5y"
WINDOW  = 60
Z_ENTRY = 1.5
Z_EXIT  = 0.25
Z_STOP  = 2.5
CAPITAL = 20_000.0
MIN_SURVIVORS = 3

print(f"Fetching {ETF} + {STOCKS} ({PERIOD})...")
etf_px = fetch_price(ETF, period=PERIOD)
prices = fetch_prices_bulk(STOCKS, period=PERIOD)
cdf    = pd.DataFrame(prices).dropna()
ea     = etf_px.reindex(cdf.index).dropna()
cdf    = cdf.reindex(ea.index)

# --- Rolling OLS: survivor count per bar -------------------------------------
print("Computing rolling OLS survivor counts...")
y_all = np.log(ea.values).astype(float)
X_all = np.log(cdf.values).astype(float)
n     = len(ea)

survivor_counts = pd.Series(np.nan, index=ea.index)
for t in range(WINDOW, n):
    X_aug  = np.column_stack([np.ones(WINDOW), X_all[t - WINDOW : t]])
    coeffs, _, _, _ = np.linalg.lstsq(X_aug, y_all[t - WINDOW : t], rcond=None)
    n_pos  = int((coeffs[1:] > 0).sum())
    survivor_counts.iloc[t] = n_pos

# --- Baseline backtest -------------------------------------------------------
print("Running baseline backtest...")
spread = rolling_basket_spread(ea, cdf, window=WINDOW)
signals, _ = generate_basket_signals(
    spread, window=WINDOW,
    z_entry=Z_ENTRY, z_exit=Z_EXIT, z_stop=Z_STOP,
)
trades_df, equity_curve, metrics = run_basket_backtest(
    signals, spread, capital=CAPITAL, cost_bps=5.0,
    n_stocks=len(STOCKS),
)

if trades_df.empty:
    print("No trades generated.")
    sys.exit(0)

# --- Tag each trade with survivor count at entry -----------------------------
trades_df = trades_df.copy()
trades_df["survivors"] = trades_df["entry_date"].map(
    survivor_counts.reindex(trades_df["entry_date"]).values.__iter__().__next__
    if False else survivor_counts
)
# map entry_date -> survivor count (forward-fill gaps)
sv_filled = survivor_counts.ffill()
trades_df["survivors"] = trades_df["entry_date"].apply(
    lambda d: sv_filled.get(d, np.nan)
)
trades_df["blocked"] = trades_df["survivors"] < MIN_SURVIVORS

n_blocked     = int(trades_df["blocked"].sum())
n_non_blocked = len(trades_df) - n_blocked

print(f"\n{'='*55}")
print(f"Backtest: {ETF}  |  {PERIOD}  |  window={WINDOW}")
print(f"{'='*55}")

# --- Full baseline metrics ---------------------------------------------------
def summarise(label, df, cap):
    if df.empty:
        print(f"\n{label}: no trades")
        return
    pnls    = df["pnl"].values
    wins    = pnls[pnls > 0]
    losses  = pnls[pnls < 0]
    total_r = df["pnl"].sum() / cap
    avg_pnl = df["pnl"].mean()
    win_r   = len(wins) / len(df) if len(df) else float("nan")
    avg_win  = wins.mean()  if len(wins)   else float("nan")
    avg_loss = losses.mean() if len(losses) else float("nan")
    print(f"\n{label}  ({len(df)} trades)")
    print(f"  Total return  : {total_r:+.2%}")
    print(f"  Avg PnL/trade : ${avg_pnl:+,.2f}")
    print(f"  Win rate      : {win_r:.1%}")
    print(f"  Avg win       : ${avg_win:+,.2f}")
    print(f"  Avg loss      : ${avg_loss:+,.2f}")
    if len(losses):
        print(f"  Profit factor : {wins.sum() / abs(losses.sum()):.2f}" if len(wins) else "  Profit factor : n/a")

summarise("BASELINE (all trades)", trades_df, CAPITAL)
print(f"\n  Sharpe        : {metrics['sharpe']:.2f}")
print(f"  Max drawdown  : {metrics['max_drawdown']:.1%}")

# --- Split: blocked vs non-blocked -------------------------------------------
blocked_df     = trades_df[trades_df["blocked"]]
non_blocked_df = trades_df[~trades_df["blocked"]]

summarise("NON-BLOCKED (survivors >= 3)", non_blocked_df, CAPITAL)
summarise("BLOCKED     (survivors < 3) ", blocked_df,     CAPITAL)

# --- Rebuild equity curve excluding blocked entries --------------------------
print(f"\n--- Simulated equity with blocked trades removed ---")
non_blocked_trades = non_blocked_df.copy()

if not non_blocked_trades.empty:
    all_dates = pd.bdate_range(
        start=non_blocked_trades["entry_date"].min(),
        end=non_blocked_trades["exit_date"].max(),
    )
    spread_aligned = spread.reindex(all_dates).ffill()
    daily_pos = pd.Series(0.0, index=all_dates)
    for _, tr in non_blocked_trades.iterrows():
        mask = (all_dates > tr["entry_date"]) & (all_dates <= tr["exit_date"])
        daily_pos[mask] += tr["direction"] * tr["notional"]

    cost_rate  = (5.0 / 10_000) * np.sqrt(len(STOCKS) / 5.0)
    daily_mtm  = daily_pos * spread_aligned.diff().fillna(0.0)
    exit_costs = non_blocked_trades.groupby("exit_date")["notional"].sum() * cost_rate
    daily_mtm  = daily_mtm.subtract(exit_costs.reindex(all_dates, fill_value=0.0))
    eq_nb      = CAPITAL + daily_mtm.cumsum()

    from src.backtest.metrics import compute_metrics
    eq_nb_df   = eq_nb.to_frame("equity")
    eq_nb_df.index.name = "date"
    m_nb       = compute_metrics(eq_nb_df, non_blocked_trades, CAPITAL)

    print(f"  Sharpe        : {m_nb['sharpe']:.2f}  (baseline: {metrics['sharpe']:.2f})")
    print(f"  Max drawdown  : {m_nb['max_drawdown']:.1%}  (baseline: {metrics['max_drawdown']:.1%})")
    print(f"  Total return  : {m_nb['total_return']:+.2%}  (baseline: {metrics['total_return']:+.2%})")
    print(f"  Trade count   : {len(non_blocked_trades)}  (baseline: {len(trades_df)})")

# --- Show the blocked trades detail ------------------------------------------
if not blocked_df.empty:
    print(f"\nBlocked trade detail:")
    print(f"  {'Entry':12s} {'Exit':12s} {'Survivors':>9} {'PnL':>10} {'PnL%':>7}")
    print(f"  {'-'*12} {'-'*12} {'-'*9} {'-'*10} {'-'*7}")
    for _, r in blocked_df.sort_values("entry_date").iterrows():
        print(f"  {str(r['entry_date'].date()):12s} "
              f"{str(r['exit_date'].date()):12s} "
              f"{int(r['survivors']) if not np.isnan(r['survivors']) else '?':>9} "
              f"${r['pnl']:>+9,.2f} "
              f"{r['pnl_pct']:>+6.2%}")

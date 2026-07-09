"""Basket / ETF arbitrage backtest — spread-based P&L."""

import math as _math

import numpy as np
import pandas as pd


def run_basket_backtest(
    signals_df: pd.DataFrame,
    spread: pd.Series,
    capital: float = 20_000.0,
    cost_bps: float = 5.0,
    n_stocks: int = 1,
    max_hold_days: int = 0,
    vol_target: float = 0.0,
) -> tuple:
    """
    Spread-based backtest for basket/ETF arbitrage.

    The spread is in log-price units (e.g. 0.01 = 1% basis deviation).
    Position sizing: notional = capital so that a 1% basis move earns 1% of capital,
    unless vol_target > 0, in which case notional is scaled by target / spread_vol.

    cost_bps is scaled by sqrt(n_stocks / 5) to reflect execution overhead when
    trading many instruments simultaneously.

    Parameters
    ----------
    max_hold_days : Force-close positions held longer than this many calendar days
                    (0 = off).
    vol_target    : Annualised spread P&L volatility target as a fraction of capital
                    (0 = off, e.g. 0.10 = 10%). Notional is capped at 3× capital.

    Returns
    -------
    (trades_df, equity_curve, metrics)
    """
    from src.backtest.metrics import compute_metrics

    cost_scale = _math.sqrt(max(n_stocks, 1) / 5.0)
    cost_rate  = cost_bps / 10_000 * cost_scale

    # Precompute annualised spread volatility for vol targeting
    if vol_target > 0:
        spread_vol_series = spread.rolling(30).std() * _math.sqrt(252)
    else:
        spread_vol_series = None

    trades     = []
    open_pos   = None
    last_valid = None  # (date, spread) of the most recent non-NaN bar seen

    for date, row in signals_df.iterrows():
        sig = row["signal"]
        s   = spread.get(date, np.nan)
        if np.isnan(s):
            continue
        last_valid = (date, s)

        if open_pos is not None:
            # Time stop: force-exit if held too long
            exit_type = None
            if max_hold_days > 0 and (date - open_pos["entry_date"]).days >= max_hold_days:
                exit_type = "time_stop"
            elif sig in ("exit", "stop"):
                exit_type = sig

            if exit_type:
                trade_notional = open_pos["notional"]
                gross = open_pos["direction"] * (s - open_pos["entry_spread"]) * trade_notional
                cost  = trade_notional * cost_rate
                pnl   = round(gross - cost, 4)
                trades.append({
                    "entry_date":   open_pos["entry_date"],
                    "exit_date":    date,
                    "exit_type":    exit_type,
                    "direction":    open_pos["direction"],
                    "entry_spread": open_pos["entry_spread"],
                    "exit_spread":  s,
                    "notional":     trade_notional,
                    "pnl":          pnl,
                    "pnl_pct":      round(pnl / capital, 6),
                })
                open_pos = None
                continue

        if open_pos is None and sig in ("long_spread", "short_spread"):
            # Compute per-trade notional
            if vol_target > 0 and spread_vol_series is not None:
                sv = spread_vol_series.get(date, np.nan)
                if not np.isnan(sv) and sv > 1e-8:
                    trade_notional = min(capital * vol_target / sv, 3 * capital)
                else:
                    trade_notional = capital
            else:
                trade_notional = capital

            open_pos = {
                "entry_date":   date,
                "direction":    1 if sig == "long_spread" else -1,
                "entry_spread": s,
                "notional":     trade_notional,
            }

    # Force-close any position still open at the end of the window (e.g. an
    # EDGAR constituent segment boundary) instead of silently dropping it --
    # mark it to the last valid spread bar and charge the normal exit cost.
    if open_pos is not None and last_valid is not None:
        date, s = last_valid
        trade_notional = open_pos["notional"]
        gross = open_pos["direction"] * (s - open_pos["entry_spread"]) * trade_notional
        cost  = trade_notional * cost_rate
        pnl   = round(gross - cost, 4)
        trades.append({
            "entry_date":   open_pos["entry_date"],
            "exit_date":    date,
            "exit_type":    "data_end",
            "direction":    open_pos["direction"],
            "entry_spread": open_pos["entry_spread"],
            "exit_spread":  s,
            "notional":     trade_notional,
            "pnl":          pnl,
            "pnl_pct":      round(pnl / capital, 6),
        })
        open_pos = None

    if not trades:
        eq = pd.DataFrame(
            {"equity": pd.Series(dtype=float)},
            index=pd.DatetimeIndex([], name="date"),
        )
        return pd.DataFrame(), eq, _empty_metrics()

    trades_df = pd.DataFrame(trades)

    # Mark-to-market equity: weight each day by the per-trade notional
    all_dates = pd.bdate_range(
        start=trades_df["entry_date"].min(),
        end=trades_df["exit_date"].max(),
    )
    spread_aligned = spread.reindex(all_dates).ffill()

    # Daily signed notional position (accounts for variable sizing)
    daily_notional_pos = pd.Series(0.0, index=all_dates)
    for _, tr in trades_df.iterrows():
        mask = (all_dates > tr["entry_date"]) & (all_dates <= tr["exit_date"])
        daily_notional_pos[mask] += tr["direction"] * tr["notional"]

    daily_mtm = daily_notional_pos * spread_aligned.diff().fillna(0.0)

    # Deduct transaction costs on exit bars (scaled by per-trade notional)
    exit_costs = trades_df.groupby("exit_date")["notional"].sum() * cost_rate
    daily_mtm  = daily_mtm.subtract(exit_costs.reindex(all_dates, fill_value=0.0))

    equity_series = capital + daily_mtm.cumsum()
    equity_series.index.name = "date"
    equity_curve = equity_series.to_frame("equity")

    metrics = compute_metrics(equity_curve, trades_df, capital)
    return trades_df, equity_curve, metrics


def run_basket_backtest_segmented(
    segments: list,
    capital: float = 20_000.0,
    cost_bps: float = 5.0,
    n_stocks: int = 1,
    max_hold_days: int = 0,
    vol_target: float = 0.0,
) -> tuple:
    """
    Multi-segment basket backtest with position continuity across constituent changes.

    Parameters
    ----------
    segments : list of (seg_start, seg_end, signals_df, spread)
        Chronologically ordered constituent periods. Each spread series should
        extend slightly past seg_end (by max_hold_days) so that positions open
        at a changeover can be tracked to a natural exit.

    At each segment boundary, if a position is open it is NOT force-closed.
    The old spread is used for P&L tracking; the new segment's signals drive
    exit detection. Once the position closes, new entries use the new basket.
    """
    import math as _math
    from src.backtest.metrics import compute_metrics

    cost_scale = _math.sqrt(max(n_stocks, 1) / 5.0)
    cost_rate  = cost_bps / 10_000 * cost_scale

    trades      = []
    open_pos    = None
    open_spread = None   # spread locked in at entry — may extend past its seg_end
    open_seg    = -1     # index of the segment where the open position was entered

    for seg_idx, (seg_start, seg_end, signals_df, spread) in enumerate(segments):
        if vol_target > 0:
            spread_vol = spread.rolling(30).std() * _math.sqrt(252)
        else:
            spread_vol = None

        entry_start = seg_start

        # Phase A: carry open position from a prior segment using the old spread
        if open_pos is not None and open_seg != seg_idx:
            for date, row in signals_df.iterrows():
                if date < seg_start:
                    continue
                s = open_spread.get(date, np.nan)
                if np.isnan(s):
                    s = spread.get(date, np.nan)
                if np.isnan(s):
                    continue

                exit_type = None
                if max_hold_days > 0 and (date - open_pos["entry_date"]).days >= max_hold_days:
                    exit_type = "time_stop"
                elif row["signal"] in ("exit", "stop"):
                    exit_type = row["signal"]

                if exit_type:
                    pnl = round(
                        open_pos["direction"] * (s - open_pos["entry_spread"]) * open_pos["notional"]
                        - open_pos["notional"] * cost_rate,
                        4,
                    )
                    trades.append({
                        "entry_date":   open_pos["entry_date"],
                        "exit_date":    date,
                        "exit_type":    exit_type,
                        "direction":    open_pos["direction"],
                        "entry_spread": open_pos["entry_spread"],
                        "exit_spread":  s,
                        "notional":     open_pos["notional"],
                        "pnl":          pnl,
                        "pnl_pct":      round(pnl / capital, 6),
                        "seg_idx":      open_seg,
                    })
                    open_pos    = None
                    open_spread = None
                    open_seg    = -1
                    entry_start = date
                    break

            if open_pos is not None:
                continue   # still in old position — skip new entries this segment

        # Phase B: normal entry/exit for this segment's date range
        for date, row in signals_df.iterrows():
            if date < entry_start or date > seg_end:
                continue
            sig = row["signal"]
            s   = spread.get(date, np.nan)
            if np.isnan(s):
                continue

            if open_pos is not None:
                exit_type = None
                if max_hold_days > 0 and (date - open_pos["entry_date"]).days >= max_hold_days:
                    exit_type = "time_stop"
                elif sig in ("exit", "stop"):
                    exit_type = sig

                if exit_type:
                    pnl = round(
                        open_pos["direction"] * (s - open_pos["entry_spread"]) * open_pos["notional"]
                        - open_pos["notional"] * cost_rate,
                        4,
                    )
                    trades.append({
                        "entry_date":   open_pos["entry_date"],
                        "exit_date":    date,
                        "exit_type":    exit_type,
                        "direction":    open_pos["direction"],
                        "entry_spread": open_pos["entry_spread"],
                        "exit_spread":  s,
                        "notional":     open_pos["notional"],
                        "pnl":          pnl,
                        "pnl_pct":      round(pnl / capital, 6),
                        "seg_idx":      open_seg,
                    })
                    open_pos    = None
                    open_spread = None
                    open_seg    = -1

            elif sig in ("long_spread", "short_spread"):
                if vol_target > 0 and spread_vol is not None:
                    sv = spread_vol.get(date, np.nan)
                    trade_notional = (
                        min(capital * vol_target / sv, 3 * capital)
                        if not np.isnan(sv) and sv > 1e-8 else capital
                    )
                else:
                    trade_notional = capital

                open_pos    = {
                    "entry_date":   date,
                    "direction":    1 if sig == "long_spread" else -1,
                    "entry_spread": s,
                    "notional":     trade_notional,
                }
                open_spread = spread
                open_seg    = seg_idx

    if not trades:
        eq = pd.DataFrame(
            {"equity": pd.Series(dtype=float)},
            index=pd.DatetimeIndex([], name="date"),
        )
        return pd.DataFrame(), eq, _empty_metrics()

    trades_df = pd.DataFrame(trades)

    # Mark-to-market equity: each trade uses its own segment's spread for daily P&L
    all_dates = pd.bdate_range(
        start=trades_df["entry_date"].min(),
        end=trades_df["exit_date"].max(),
    )
    daily_mtm = pd.Series(0.0, index=all_dates)

    for _, tr in trades_df.iterrows():
        seg_spread = segments[int(tr["seg_idx"])][3]
        s_aligned  = seg_spread.reindex(all_dates).ffill()
        mask = (all_dates > tr["entry_date"]) & (all_dates <= tr["exit_date"])
        daily_mtm[mask] += tr["direction"] * tr["notional"] * s_aligned.diff()[mask]

    exit_costs = trades_df.groupby("exit_date")["notional"].sum() * cost_rate
    daily_mtm  = daily_mtm.subtract(exit_costs.reindex(all_dates, fill_value=0.0))

    equity_series = capital + daily_mtm.cumsum()
    equity_series.index.name = "date"
    equity_curve = equity_series.to_frame("equity")

    metrics = compute_metrics(equity_curve, trades_df, capital)
    return trades_df, equity_curve, metrics


def _empty_metrics() -> dict:
    return {
        "total_return":  0.0,
        "cagr":          0.0,
        "sharpe":        0.0,
        "sortino":       0.0,
        "max_drawdown":  0.0,
        "calmar":        float("nan"),
        "n_trades":      0,
        "win_rate":      float("nan"),
        "avg_win":       float("nan"),
        "avg_loss":      float("nan"),
        "profit_factor": float("nan"),
        "avg_hold_days": float("nan"),
    }

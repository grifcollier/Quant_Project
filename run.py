"""CLI entry point for the quant trading system."""

import argparse
import sys
import tempfile
import webbrowser

import pandas as pd

from src.data.fetcher import fetch_pair
from src.analytics.stationarity import adf_test, compute_half_life
from src.strategies.pairs.config import DEFAULT_PARAMS, PAIRS
from src.strategies.pairs.signals import compute_zscore, generate_signals
from src.strategies.pairs.spread import compute_hedge_ratio, compute_spread
from src.strategies.pairs.viz import plot_all_dashboard, plot_pair_charts, plot_pair_interpretation, plot_pair_stats


def _show(fig, title: str) -> None:
    """Open a Plotly figure in the browser with a named tab title."""
    html = fig.to_html(full_html=True, include_plotlyjs="cdn")
    html = html.replace("<head>", f"<head><title>{title}</title>", 1)
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(html)
        path = f.name
    webbrowser.open(f"file:///{path}")


def _run_pairs(args):
    if args.all:
        _pairs_all(args.period, args.window, args.z_entry, args.z_exit, args.z_stop)
    else:
        parts = args.pair.split("/")
        if len(parts) != 2:
            print("ERROR: --pair must be in the format A/B, e.g. KO/PEP")
            sys.exit(1)
        _pairs_single(parts[0].upper(), parts[1].upper(),
                      args.period, args.window, args.z_entry, args.z_exit, args.z_stop,
                      backtest=args.backtest)


def _pairs_single(ticker_a, ticker_b, period, window, z_entry, z_exit, z_stop, backtest=False):
    print(f"Fetching {ticker_a}/{ticker_b}...")

    df = fetch_pair(ticker_a, ticker_b, period=period)
    if df.empty:
        print("ERROR: No data returned.")
        return

    beta    = compute_hedge_ratio(df["close_a"], df["close_b"])
    spread  = compute_spread(df["close_a"], df["close_b"], beta)
    adf     = adf_test(spread)
    hl      = compute_half_life(spread)
    zscore  = compute_zscore(spread, window=window)
    signals = generate_signals(zscore, z_entry=z_entry, z_exit=z_exit, z_stop=z_stop)

    params = {
        "period": period, "rolling_window": window,
        "z_entry": z_entry, "z_exit": z_exit, "z_stop": z_stop,
    }

    pair = f"{ticker_a}/{ticker_b}"
    print("Opening windows...")
    _show(plot_pair_stats(ticker_a, ticker_b, period, beta, adf, hl, signals, params),
          f"{pair} — Stats")
    _show(plot_pair_interpretation(ticker_a, ticker_b, period, beta, adf, hl, signals, params),
          f"{pair} — Interpretation")
    _show(plot_pair_charts(df, ticker_a, ticker_b, spread, beta, signals, params),
          f"{pair} — Charts")

    if backtest:
        from src.data.fetcher import fetch_pair_ohlcv
        from src.strategies.pairs.backtest import run_pairs_backtest
        from src.strategies.pairs.viz import (
            plot_equity_curve, plot_trade_pnl, plot_backtest_metrics,
            plot_backtest_interpretation,
        )
        print("Running backtest...")
        df_ohlcv = fetch_pair_ohlcv(ticker_a, ticker_b, period=period)
        trades, equity_curve, bt_metrics = run_pairs_backtest(
            ticker_a, ticker_b, signals, df_ohlcv, beta, capital_per_leg=10_000.0,
        )
        print(
            f"Backtest: {bt_metrics['n_trades']} trades  |  "
            f"{bt_metrics['total_return']:.1%} return  |  "
            f"Sharpe {bt_metrics['sharpe']:.2f}"
        )
        _show(plot_equity_curve(equity_curve, trades, ticker_a, ticker_b, 20_000.0),
              f"{pair} — Equity Curve")
        _show(plot_trade_pnl(trades, ticker_a, ticker_b),
              f"{pair} — Trade P&L")
        _show(plot_backtest_metrics(bt_metrics, trades, ticker_a, ticker_b, params),
              f"{pair} — Backtest Metrics")
        _show(plot_backtest_interpretation(bt_metrics, trades, ticker_a, ticker_b, params, hl),
              f"{pair} — Backtest Explanation")


def _pairs_all(period, window, z_entry, z_exit, z_stop):
    rows = []
    for pair in PAIRS:
        ta, tb = pair["ticker_a"], pair["ticker_b"]
        print(f"  Scanning {ta}/{tb}...")
        try:
            df      = fetch_pair(ta, tb, period=period)
            beta    = compute_hedge_ratio(df["close_a"], df["close_b"])
            spread  = compute_spread(df["close_a"], df["close_b"], beta)
            adf     = adf_test(spread)
            hl      = compute_half_life(spread)
            zscore  = compute_zscore(spread, window=window)
            signals = generate_signals(zscore, z_entry=z_entry, z_exit=z_exit, z_stop=z_stop)
            counts  = signals["signal"].value_counts().to_dict()
            exits   = counts.get("exit", 0)
            stops   = counts.get("stop", 0)
            total   = exits + stops
            rows.append({
                "pair":          f"{ta}/{tb}",
                "sector":        pair["sector"],
                "beta":          round(beta, 3),
                "adf_pval":      adf["p_value"],
                "stationary":    "yes" if adf["is_stationary"] else "no",
                "half_life":     hl,
                "long_entries":  counts.get("long_spread", 0),
                "short_entries": counts.get("short_spread", 0),
                "exits":         exits,
                "stops":         stops,
                "stop_rate":     f"{stops / total:.0%}" if total > 0 else "n/a",
            })
        except Exception as e:
            print(f"  ERROR on {ta}/{tb}: {e}")

    print("Opening summary...")
    _show(plot_all_dashboard(pd.DataFrame(rows)), "All Pairs — Summary")


def _register_pairs(subparsers):
    p = DEFAULT_PARAMS
    parser = subparsers.add_parser("pairs", help="Pairs trading strategy")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pair", metavar="A/B", help="Single pair, e.g. KO/PEP")
    group.add_argument("--all",  action="store_true", help="Scan all pairs in config")

    parser.add_argument("--period",  default=p["period"],         help=f"Data lookback (default: {p['period']})")
    parser.add_argument("--window",  default=p["rolling_window"], type=int,   help=f"Rolling window in days (default: {p['rolling_window']})")
    parser.add_argument("--z-entry", default=p["z_entry"],        type=float, help=f"Entry threshold (default: {p['z_entry']})")
    parser.add_argument("--z-exit",  default=p["z_exit"],         type=float, help=f"Exit threshold (default: {p['z_exit']})")
    parser.add_argument("--z-stop",  default=p["z_stop"],         type=float, help=f"Stop-loss threshold (default: {p['z_stop']})")
    parser.add_argument("--backtest", action="store_true", default=False,
                        help="Run backtest and show equity curve + metrics")
    parser.set_defaults(func=_run_pairs)


def main():
    parser = argparse.ArgumentParser(description="Quant Trading CLI")
    subparsers = parser.add_subparsers(dest="strategy", metavar="STRATEGY")
    subparsers.required = True

    _register_pairs(subparsers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

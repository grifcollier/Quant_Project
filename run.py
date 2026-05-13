"""CLI entry point for the quant trading system."""

import argparse
import sys
import tempfile
import webbrowser

import pandas as pd

from src.data.fetcher import fetch_pair, fetch_price
from src.analytics.stationarity import adf_test, compute_half_life
from src.strategies.pairs.config import DEFAULT_PARAMS, PAIRS, SCAN_UNIVERSES
from src.strategies.pairs.signals import compute_zscore, generate_signals
from src.strategies.pairs.spread import (
    compute_hedge_ratio, compute_spread,
    compute_rolling_hedge_ratio, compute_rolling_spread,
)
from src.strategies.pairs.viz import (
    plot_all_dashboard, plot_pair_charts, plot_pair_interpretation,
    plot_pair_stats, plot_scan_results,
)


def _show(fig, title: str) -> None:
    """Open a Plotly figure in the browser with a named tab title."""
    html = fig.to_html(full_html=True, include_plotlyjs=True)
    html = html.replace("<head>", f"<head><title>{title}</title>", 1)
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(html)
        path = f.name
    webbrowser.open(f"file:///{path}")


def _run_pairs(args):
    if args.scan:
        _pairs_scan(args)
    elif args.all:
        _pairs_all(args.period, args.window, args.z_entry, args.z_exit, args.z_stop)
    else:
        parts = args.pair.split("/")
        if len(parts) != 2:
            print("ERROR: --pair must be in the format A/B, e.g. KO/PEP")
            sys.exit(1)
        _pairs_single(parts[0].upper(), parts[1].upper(),
                      args.period, args.window, args.z_entry, args.z_exit, args.z_stop,
                      backtest=args.backtest,
                      rolling_beta=args.rolling_beta,
                      beta_window=args.beta_window)


def _pairs_single(
    ticker_a, ticker_b, period, window, z_entry, z_exit, z_stop,
    backtest=False, rolling_beta=False, beta_window=252,
):
    print(f"Fetching {ticker_a}/{ticker_b}...")

    df = fetch_pair(ticker_a, ticker_b, period=period)
    if df.empty:
        print("ERROR: No data returned.")
        return

    if rolling_beta:
        print(f"Using rolling hedge ratio (window={beta_window} days)...")
        rolling_hr = compute_rolling_hedge_ratio(df["close_a"], df["close_b"], window=beta_window)
        spread     = compute_rolling_spread(df["close_a"], df["close_b"], rolling_hr)
        # Trim df to match the shorter spread index (rolling warm-up removes leading rows)
        df         = df.loc[spread.index]
        beta_display = float(rolling_hr.dropna().iloc[-1])
        beta       = rolling_hr  # Series passed to backtest for per-trade sizing
    else:
        beta_display = compute_hedge_ratio(df["close_a"], df["close_b"])
        spread       = compute_spread(df["close_a"], df["close_b"], beta_display)
        beta         = beta_display

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
    _show(plot_pair_stats(ticker_a, ticker_b, period, beta_display, adf, hl, signals, params),
          f"{pair} — Stats")
    _show(plot_pair_interpretation(ticker_a, ticker_b, period, beta_display, adf, hl, signals, params),
          f"{pair} — Interpretation")
    _show(plot_pair_charts(df, ticker_a, ticker_b, spread, beta_display, signals, params),
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
        # Align OHLCV to the (possibly trimmed) spread window
        df_ohlcv = df_ohlcv.loc[df_ohlcv.index.isin(spread.index)]
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


def _pairs_scan(args):
    from src.analytics.cointegration import scan_universe
    from src.data.fetcher import fetch_prices_bulk

    period      = args.period
    min_corr    = args.min_correlation

    # ── Resolve ticker list ───────────────────────────────────────────────────
    if args.tickers_file:
        path = args.tickers_file
        if not __import__("os").path.exists(path):
            print(f"ERROR: File not found: {path}")
            sys.exit(1)
        with open(path) as f:
            tickers = [
                line.strip().upper() for line in f
                if line.strip() and not line.startswith("#")
            ]
        universe_name = f"File: {path}"
    elif args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        universe_name = "Custom: " + ", ".join(tickers)
    elif args.universe:
        name = args.universe.lower()
        if name not in SCAN_UNIVERSES:
            available = ", ".join(SCAN_UNIVERSES.keys())
            print(f"ERROR: Unknown universe '{args.universe}'. Available: {available}")
            sys.exit(1)
        tickers = SCAN_UNIVERSES[name]
        universe_name = args.universe.capitalize()
    else:
        tickers = list({t for p in PAIRS for t in (p["ticker_a"], p["ticker_b"])})
        universe_name = "Configured Pairs"

    # ── Fetch prices (bulk for speed) ─────────────────────────────────────────
    n_total_pairs = len(tickers) * (len(tickers) - 1) // 2
    print(f"Fetching {len(tickers)} tickers ({period})...  "
          f"[{n_total_pairs} possible pairs]")
    prices = fetch_prices_bulk(tickers, period=period)
    failed = len(tickers) - len(prices)
    if failed:
        print(f"  WARNING: {failed} ticker(s) could not be fetched and will be skipped.")

    # ── Scan ──────────────────────────────────────────────────────────────────
    scan_df = scan_universe(
        list(prices.keys()), prices,
        min_correlation=min_corr,
        verbose=True,
    )

    passing = int(scan_df["passes"].sum()) if not scan_df.empty else 0

    # ── Terminal results table ────────────────────────────────────────────────
    COL = {"pair": 10, "corr": 6, "beta": 8, "adf_pval": 11, "stationary": 12, "half_life": 13, "passes": 8}
    HDR = {"pair": "Pair", "corr": "Corr", "beta": "Beta", "adf_pval": "ADF p-val",
           "stationary": "Stationary", "half_life": "Half-Life", "passes": "Passes"}

    header_line = "  " + "  ".join(f"{HDR[c]:<{w}}" for c, w in COL.items())
    divider     = "  " + "  ".join("-" * w for w in COL.values())
    print(f"\n  Universe: {universe_name}  |  {len(scan_df)} pairs tested\n")
    print(header_line)
    print(divider)
    for _, row in scan_df.iterrows():
        hl_str   = f"{row['half_life']:.1f} days" if row["half_life"] != float("inf") else "inf"
        stat_str = "Yes" if row["is_stationary"] else "No"
        pass_str = "[PASS]" if row["passes"] else "[FAIL]"
        corr_str = f"{row['correlation']:.3f}" if "correlation" in row.index else "n/a"
        print("  " + "  ".join([
            f"{row['pair']:<{COL['pair']}}",
            f"{corr_str:<{COL['corr']}}",
            f"{row['beta']:<{COL['beta']}.4f}",
            f"{row['adf_pval']:<{COL['adf_pval']}.4f}",
            f"{stat_str:<{COL['stationary']}}",
            f"{hl_str:<{COL['half_life']}}",
            f"{pass_str:<{COL['passes']}}",
        ]))
    print(divider)
    print(f"  {passing}/{len(scan_df)} pairs pass filters (ADF p < 0.10, half-life 5-100 days)\n")

    _show(plot_scan_results(scan_df, universe_name), f"Scanner  --  {universe_name}")


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
    group.add_argument("--scan", action="store_true", help="Scan a universe for cointegrated pairs")

    parser.add_argument("--period",  default=p["period"],         help=f"Data lookback (default: {p['period']})")
    parser.add_argument("--window",  default=p["rolling_window"], type=int,   help=f"Rolling window in days (default: {p['rolling_window']})")
    parser.add_argument("--z-entry", default=p["z_entry"],        type=float, help=f"Entry threshold (default: {p['z_entry']})")
    parser.add_argument("--z-exit",  default=p["z_exit"],         type=float, help=f"Exit threshold (default: {p['z_exit']})")
    parser.add_argument("--z-stop",  default=p["z_stop"],         type=float, help=f"Stop-loss threshold (default: {p['z_stop']})")
    parser.add_argument("--backtest", action="store_true", default=False,
                        help="Run backtest and show equity curve + metrics")
    # Rolling hedge ratio flags (only relevant with --pair)
    parser.add_argument("--rolling-beta", action="store_true", default=False,
                        help="Use rolling hedge ratio — removes look-ahead bias from backtest")
    parser.add_argument("--beta-window", type=int, default=252,
                        help="Window in days for rolling beta estimation (default: 252)")
    # Universe scan flags (only relevant with --scan)
    parser.add_argument("--universe", metavar="NAME",
                        help=f"Named universe for --scan. Options: {', '.join(SCAN_UNIVERSES)}")
    parser.add_argument("--tickers", metavar="A,B,C",
                        help="Comma-separated tickers for --scan, e.g. GS,MS,JPM")
    parser.add_argument("--tickers-file", metavar="PATH",
                        help="Path to a text file with one ticker per line for --scan")
    parser.add_argument("--min-correlation", type=float, default=0.80, metavar="R",
                        help="Min absolute return correlation to test a pair (default: 0.80). "
                             "Set to 0 to test all pairs.")
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

"""CLI entry point for the quant trading system."""

import argparse
import sys
import tempfile
import webbrowser

import numpy as np
import pandas as pd

from src.data.fetcher import fetch_pair, fetch_price
from src.analytics.stationarity import adf_test, compute_half_life
from src.strategies.pairs.config import DEFAULT_PARAMS, PAIRS, SCAN_UNIVERSES
from src.strategies.pairs.signals import compute_zscore, generate_signals
from src.strategies.pairs.spread import (
    compute_hedge_ratio, compute_spread,
    compute_kalman_hedge_ratio, compute_kalman_spread,
)
from src.strategies.pairs.viz import (
    plot_all_dashboard, plot_pair_charts, plot_pair_interpretation,
    plot_pair_stats, plot_scan_results,
)


_SAVE_IMAGES_DIR: str | None = None  # set by --save-images flag
_SAVE_FIGS_DIR:   str | None = None  # set by --save-figs flag


def _show(fig, title: str, static: bool = False) -> None:
    """Open a Plotly figure in the browser; export PNG/JSON if save flags are set."""
    if _SAVE_IMAGES_DIR is not None:
        import os, re
        os.makedirs(_SAVE_IMAGES_DIR, exist_ok=True)
        slug = re.sub(r"[^\w\-]", "_", title).strip("_").lower()
        out  = os.path.join(_SAVE_IMAGES_DIR, f"{slug}.png")
        fig.write_image(out, width=1400, height=800, scale=2)
        print(f"  Saved: {out}")

    if _SAVE_FIGS_DIR is not None:
        import os, re
        os.makedirs(_SAVE_FIGS_DIR, exist_ok=True)
        n = len([f for f in os.listdir(_SAVE_FIGS_DIR) if f.endswith(".json")])
        slug = re.sub(r"[^\w\-]", "_", title).strip("_").lower()
        out = os.path.join(_SAVE_FIGS_DIR, f"{n + 1:03d}_{slug}.json")
        with open(out, "w") as f:
            f.write(fig.to_json())
        print(f"  Saved fig: {out}")
        return  # skip browser when saving figures

    html = fig.to_html(full_html=True, include_plotlyjs=True)
    html = html.replace("<head>", f"<head><title>{title}</title>", 1)
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(html)
        path = f.name
    webbrowser.open(f"file:///{path}")


def _print_mc_summary(mc: dict) -> None:
    import numpy as np
    rows = [
        ("Return", "returns",   ".1%"),
        ("Max DD", "drawdowns", ".1%"),
    ]
    for label, key, fmt in rows:
        p5, p50, p95 = np.percentile(mc[key], [5, 50, 95])
        print(f"  {label:8s}  5th/50th/95th: {p5:{fmt}} / {p50:{fmt}} / {p95:{fmt}}")


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
                      kalman_delta=args.kalman_delta,
                      max_hold_days=args.max_hold_days,
                      dollar_stop_pct=args.dollar_stop,
                      test_period=args.test_period,
                      walk_forward=getattr(args, "walk_forward", None),
                      data_provider=getattr(args, "data_provider", "yfinance"))


_PERIOD_BARS = {
    "3mo": 63, "6mo": 126, "1y": 252, "2y": 504, "5y": 1260, "10y": 2520,
}


def _pairs_single(
    ticker_a, ticker_b, period, window, z_entry, z_exit, z_stop,
    backtest=False, kalman_delta=1e-4,
    max_hold_days=0, dollar_stop_pct=5.0,
    test_period=None, walk_forward=None,
    data_provider="yfinance",
):
    print(f"Fetching {ticker_a}/{ticker_b} via {data_provider}...")

    if data_provider == "alpaca":
        from src.data.fetcher import fetch_prices_bulk
        prices = fetch_prices_bulk([ticker_a, ticker_b], period=period, provider="alpaca")
        if ticker_a not in prices or ticker_b not in prices:
            print("ERROR: Could not fetch one or both tickers from Alpaca.")
            return
        df = pd.DataFrame({"close_a": prices[ticker_a], "close_b": prices[ticker_b]}).dropna()
        df.index.name = "date"
    else:
        df = fetch_pair(ticker_a, ticker_b, period=period)
    if df.empty:
        print("ERROR: No data returned.")
        return

    print(f"Using Kalman filter (delta={kalman_delta})...")
    kalman_params = compute_kalman_hedge_ratio(df["close_a"], df["close_b"], delta=kalman_delta)
    spread        = compute_kalman_spread(df["close_a"], df["close_b"], kalman_params)
    df            = df.loc[spread.index]
    beta_display  = float(kalman_params["beta"].iloc[-1])
    beta          = kalman_params["beta"]

    # ── Train/test split ──────────────────────────────────────────────────────
    split_date = None
    if test_period:
        n_test = _PERIOD_BARS.get(test_period, 252)
        if n_test >= len(spread) - 30:
            print(f"WARNING: --test-period '{test_period}' leaves too little training data. Ignoring.")
            test_period = None
        else:
            split_idx  = len(spread) - n_test
            split_date = spread.index[split_idx]
            spread_train = spread.iloc[:split_idx]
            print(f"Train/test split — training: {period} up to {split_date.date()}  |  test: {test_period} forward")

    spread_for_calibration = spread.iloc[:len(spread) - _PERIOD_BARS.get(test_period, 0)] \
        if test_period else spread

    adf = adf_test(spread_for_calibration)
    hl  = compute_half_life(spread_for_calibration)

    if window is None:
        suffix = "  (calibrated on training data)" if test_period else ""
        if hl != float("inf"):
            window = max(int(hl * 2.5), 20)
            print(f"Auto window: {window} days  (half-life {hl:.1f} days × 2.5){suffix}")
        else:
            window = 60
            print(f"Half-life infinite — falling back to default window: {window} days{suffix}")

    # Resolve stop parameters
    if max_hold_days > 0:
        max_hold_bars = max_hold_days
    elif hl != float("inf"):
        max_hold_bars = max(int(3 * hl), window)
    else:
        max_hold_bars = None
    max_loss_pct = dollar_stop_pct / 100 if dollar_stop_pct > 0 else None

    if max_hold_bars:
        print(f"Time stop: {max_hold_bars} days  |  Dollar stop: {f'{dollar_stop_pct:.1f}%' if max_loss_pct else 'disabled'}")

    zscore  = compute_zscore(spread, window=window)
    signals = generate_signals(zscore, z_entry=z_entry, z_exit=z_exit, z_stop=z_stop)

    params = {
        "period": period, "rolling_window": window,
        "z_entry": z_entry, "z_exit": z_exit, "z_stop": z_stop,
        "test_period": test_period,
    }

    pair = f"{ticker_a}/{ticker_b}"
    print("Opening windows...")
    _show(plot_pair_stats(ticker_a, ticker_b, period, beta_display, adf, hl, signals, params),
          f"{pair} — Stats")
    _show(plot_pair_interpretation(ticker_a, ticker_b, period, beta_display, adf, hl, signals, params),
          f"{pair} — Interpretation")
    _show(plot_pair_charts(df, ticker_a, ticker_b, spread, beta_display, signals, params,
                           split_date=split_date),
          f"{pair} — Charts")

    if backtest or walk_forward:
        from src.data.fetcher import fetch_pair_ohlcv
        from src.strategies.pairs.backtest import run_pairs_backtest
        from src.strategies.pairs.viz import (
            plot_equity_curve, plot_trade_pnl, plot_backtest_metrics,
            plot_backtest_interpretation,
        )
        from src.analytics.market_beta import compute_market_beta
        if data_provider == "alpaca":
            from src.data.alpaca_fetcher import fetch_ohlcv_bulk_alpaca
            ohlcv_dict = fetch_ohlcv_bulk_alpaca([ticker_a, ticker_b], period=period)
            _oa = ohlcv_dict.get(ticker_a, pd.DataFrame())
            _ob = ohlcv_dict.get(ticker_b, pd.DataFrame())
            _idx = _oa.index.intersection(_ob.index)
            df_ohlcv = pd.DataFrame({
                "open_a": _oa.loc[_idx, "open"], "high_a": _oa.loc[_idx, "high"],
                "low_a":  _oa.loc[_idx, "low"],  "close_a": _oa.loc[_idx, "close"],
                "volume_a": _oa.loc[_idx, "volume"],
                "open_b": _ob.loc[_idx, "open"], "high_b": _ob.loc[_idx, "high"],
                "low_b":  _ob.loc[_idx, "low"],  "close_b": _ob.loc[_idx, "close"],
                "volume_b": _ob.loc[_idx, "volume"],
            })
        else:
            df_ohlcv = fetch_pair_ohlcv(ticker_a, ticker_b, period=period)
        df_ohlcv = df_ohlcv.loc[df_ohlcv.index.isin(spread.index)]
        try:
            spy = fetch_price("SPY", period=period)
            market_beta_a = compute_market_beta(df_ohlcv["close_a"], spy)
            market_beta_b = compute_market_beta(df_ohlcv["close_b"], spy)
            print(f"Market betas at last bar — {ticker_a}: {market_beta_a.iloc[-1]:.2f}  {ticker_b}: {market_beta_b.iloc[-1]:.2f}")
        except Exception:
            market_beta_a = market_beta_b = None

        # ── Walk-forward mode ─────────────────────────────────────────────────
        if walk_forward:
            from src.backtest.engine import run_backtest
            from src.backtest.metrics import compute_metrics
            fold_bars = 252
            T = len(signals)
            fold_starts_wf, fold_ends_wf = [], []
            for k in range(walk_forward):
                start_idx = T - (walk_forward - k) * fold_bars
                end_idx   = min(T - (walk_forward - k - 1) * fold_bars, T) - 1
                if start_idx < 30:
                    continue
                fold_starts_wf.append(signals.index[start_idx])
                fold_ends_wf.append(signals.index[end_idx])

            if not fold_starts_wf:
                print("ERROR: Not enough data for walk-forward folds.")
                return

            print(f"\nRunning walk-forward validation ({len(fold_starts_wf)} folds × 1y)...")
            all_trades, fold_results = [], []
            starting_capital = 20_000.0
            for i, (fs, fe) in enumerate(zip(fold_starts_wf, fold_ends_wf), 1):
                sig_f    = signals.loc[fs:fe]
                ohlcv_f  = df_ohlcv.loc[fs:fe]
                beta_f   = beta.loc[fs:fe]
                mba_f = market_beta_a.loc[fs:fe] if market_beta_a is not None else None
                mbb_f = market_beta_b.loc[fs:fe] if market_beta_b is not None else None
                t, eq, m = run_pairs_backtest(
                    ticker_a, ticker_b, sig_f, ohlcv_f, beta_f,
                    capital_per_leg=10_000.0,
                    market_beta_a=mba_f, market_beta_b=mbb_f,
                    max_hold_bars=max_hold_bars, max_loss_pct=max_loss_pct,
                )
                fold_results.append({
                    "fold": i, "start": fs, "end": fe,
                    "n_trades": m["n_trades"],
                    "total_return": m["total_return"],
                    "sharpe": m["sharpe"],
                    "max_drawdown": m["max_drawdown"],
                })
                all_trades.append(t)
                print(f"  Fold {i} ({fs.date()} to {fe.date()}): "
                      f"{m['n_trades']} trades  |  "
                      f"{m['total_return']:.1%} return  |  "
                      f"Sharpe {m['sharpe']:.2f}")

            all_trades_df = pd.concat(all_trades) if all_trades else pd.DataFrame()
            n_total = int(sum(r["n_trades"] for r in fold_results))
            mean_ret = sum(r["total_return"] for r in fold_results) / len(fold_results)
            mean_sharpe = sum(r["sharpe"] for r in fold_results) / len(fold_results)
            print(f"\nWalk-Forward ({len(fold_results)} folds): "
                  f"{n_total} total trades  |  "
                  f"{mean_ret:.1%} avg fold return  |  "
                  f"Sharpe {mean_sharpe:.2f} avg")

            if not all_trades_df.empty:
                _show(plot_trade_pnl(all_trades_df, ticker_a, ticker_b),
                      f"{pair} — Walk-Forward Trade P&L")
            return

        # ── Single backtest (with optional test-period split) ─────────────────
        print("Running backtest...")
        if split_date is not None:
            signals_bt      = signals.loc[signals.index >= split_date]
            df_ohlcv_bt     = df_ohlcv.loc[df_ohlcv.index >= split_date]
            beta_bt         = beta.loc[beta.index >= split_date]
            mba_bt = market_beta_a.loc[market_beta_a.index >= split_date] if market_beta_a is not None else None
            mbb_bt = market_beta_b.loc[market_beta_b.index >= split_date] if market_beta_b is not None else None
            print(f"Backtesting on test period only ({test_period}: {signals_bt.index[0].date()} to {signals_bt.index[-1].date()})")
        else:
            signals_bt, df_ohlcv_bt, beta_bt = signals, df_ohlcv, beta
            mba_bt, mbb_bt = market_beta_a, market_beta_b

        trades, equity_curve, bt_metrics = run_pairs_backtest(
            ticker_a, ticker_b, signals_bt, df_ohlcv_bt, beta_bt, capital_per_leg=10_000.0,
            market_beta_a=mba_bt, market_beta_b=mbb_bt,
            max_hold_bars=max_hold_bars, max_loss_pct=max_loss_pct,
        )
        period_label = f"({test_period} test)" if test_period else ""
        print(
            f"Backtest {period_label}: {bt_metrics['n_trades']} trades  |  "
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
    provider = getattr(args, "data_provider", "yfinance")
    n_total_pairs = len(tickers) * (len(tickers) - 1) // 2
    print(f"Fetching {len(tickers)} tickers ({period}) via {provider}...  "
          f"[{n_total_pairs} possible pairs]")
    prices = fetch_prices_bulk(tickers, period=period, provider=provider)
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

    if not scan_df.empty and "correlation" in scan_df.columns:
        scan_df = scan_df.sort_values(["passes", "adf_pval"], ascending=[False, True]).reset_index(drop=True)

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

    _show(plot_scan_results(scan_df, universe_name), f"Scanner  --  {universe_name}", static=True)

    # ── Cascade stability check ───────────────────────────────────────────────
    if passing > 0:
        from src.analytics.cointegration import cascade_scan, _CASCADE_MAP
        from src.strategies.pairs.viz import plot_cascade_results
        if _CASCADE_MAP.get(period):
            print(f"Running cascade stability check on {passing} passing pair(s)...")
            passing_pairs = [
                (row["ticker_a"], row["ticker_b"])
                for _, row in scan_df[scan_df["passes"]].iterrows()
            ]
            cascade = cascade_scan(passing_pairs, prices, initial_period=period)
            _show(
                plot_cascade_results(scan_df, cascade, period, universe_name),
                f"Cascade  --  {universe_name}",
                static=True,
            )


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
    _show(plot_all_dashboard(pd.DataFrame(rows)), "All Pairs — Summary", static=True)


def _register_pairs(subparsers):
    p = DEFAULT_PARAMS
    parser = subparsers.add_parser("pairs", help="Pairs trading strategy")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pair", metavar="A/B", help="Single pair, e.g. KO/PEP")
    group.add_argument("--all",  action="store_true", help="Scan all pairs in config")
    group.add_argument("--scan", action="store_true", help="Scan a universe for cointegrated pairs")

    parser.add_argument("--period",  default=p["period"],         help=f"Data lookback (default: {p['period']})")
    parser.add_argument("--window",  default=None, type=int,
                        help="Rolling z-score window in days. Omit to auto-derive from half-life (recommended).")
    parser.add_argument("--z-entry", default=p["z_entry"],        type=float, help=f"Entry threshold (default: {p['z_entry']})")
    parser.add_argument("--z-exit",  default=p["z_exit"],         type=float, help=f"Exit threshold (default: {p['z_exit']})")
    parser.add_argument("--z-stop",  default=p["z_stop"],         type=float, help=f"Stop-loss threshold (default: {p['z_stop']})")
    parser.add_argument("--backtest", action="store_true", default=False,
                        help="Run backtest and show equity curve + metrics")
    parser.add_argument("--kalman-delta", type=float, default=1e-4, metavar="D",
                        help="Kalman filter process noise delta (default: 1e-4). Higher = faster adaptation")
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
    parser.add_argument("--test-period", default=None, metavar="PERIOD",
                        choices=["3mo", "6mo", "1y", "2y"],
                        help="Hold out the most recent PERIOD as an out-of-sample test window. "
                             "ADF, half-life, and rolling window are calibrated on the earlier data only. "
                             "Backtest runs on the test window. Example: --period 5y --test-period 1y")
    parser.add_argument("--walk-forward", default=None, type=int, metavar="N",
                        dest="walk_forward",
                        help="Run N non-overlapping 1-year OOS folds (requires --backtest; overrides --test-period)")
    parser.add_argument("--max-hold-days", type=int, default=0, metavar="N",
                        help="Time stop: close trade if still open after N days (default: 0 = auto, 3× half-life).")
    parser.add_argument("--dollar-stop", type=float, default=5.0, metavar="PCT",
                        help="Dollar stop: close trade if unrealised loss exceeds PCT%% of capital (default: 5.0). "
                             "Set to 0 to disable.")
    parser.add_argument("--data-provider", default="yfinance", metavar="PROVIDER",
                        choices=["yfinance", "alpaca"], dest="data_provider",
                        help="Price data source: yfinance (default) or alpaca "
                             "(requires ALPACA_API_KEY + ALPACA_SECRET_KEY).")
    parser.set_defaults(func=_run_pairs)


def _run_pca(args):
    from src.data.fetcher import fetch_prices_bulk
    from src.analytics.pca import rolling_pca_residuals
    from src.strategies.pca.signals import generate_pca_signals
    from src.strategies.pca.viz import (
        plot_pca_equity, plot_pca_zscore_heatmap, plot_pca_positions,
        plot_pca_walk_forward,
    )
    from src.backtest.portfolio_engine import run_portfolio_backtest, _compute_metrics

    universe_name = args.universe.lower()
    if universe_name not in SCAN_UNIVERSES:
        print(f"ERROR: Unknown universe '{args.universe}'. Available: {', '.join(SCAN_UNIVERSES)}")
        sys.exit(1)

    tickers = SCAN_UNIVERSES[universe_name]
    period  = args.period
    window  = args.window
    n_folds = getattr(args, "walk_forward", None)

    provider = getattr(args, "data_provider", "yfinance")
    print(f"Fetching {len(tickers)} tickers ({period}, provider={provider})...")
    prices_dict = fetch_prices_bulk(tickers, period=period, provider=provider)
    if len(prices_dict) < 3:
        print("ERROR: Need at least 3 tickers with data.")
        sys.exit(1)

    prices_df = pd.DataFrame(prices_dict).dropna()
    print(f"Aligned {prices_df.shape[1]} tickers over {len(prices_df)} bars.")

    returns_df = prices_df.pct_change().dropna()

    params = {
        "period": period, "window": window, "universe": universe_name.capitalize(),
        "n_factors": args.n_factors, "top_n": args.top_n,
        "z_entry": args.z_entry, "z_exit": args.z_exit, "z_stop": args.z_stop,
        "cost_bps": args.cost_bps,
    }
    universe_label = universe_name.capitalize()

    # ── Walk-forward mode ─────────────────────────────────────────────────────
    if n_folds:
        fold_bars = 252
        T = len(returns_df)
        fold_starts, fold_ends = [], []
        for k in range(n_folds):
            start_idx = T - (n_folds - k) * fold_bars
            end_idx   = min(T - (n_folds - k - 1) * fold_bars, T) - 1
            if start_idx < window + 10:
                continue
            fold_starts.append(returns_df.index[start_idx])
            fold_ends.append(returns_df.index[end_idx])

        if not fold_starts:
            print("ERROR: Not enough data for walk-forward folds. Use --period 5y or longer.")
            sys.exit(1)

        print(f"Computing rolling PCA residuals on full history (window={window}, k={args.n_factors})...")
        residuals_df = rolling_pca_residuals(returns_df, window=window, n_components=args.n_factors)

        print(f"Generating signals on full history (z_entry={args.z_entry}, top_n={args.top_n})...")
        positions_df, z_scores_df = generate_pca_signals(
            residuals_df, window=window,
            z_entry=args.z_entry, z_exit=args.z_exit, z_stop=args.z_stop,
            top_n=args.top_n,
        )

        print(f"\nRunning walk-forward validation ({len(fold_starts)} folds × 1y)...")
        equity_pieces, fold_metrics = [], []
        for i, (fs, fe) in enumerate(zip(fold_starts, fold_ends), 1):
            prices_fold    = prices_df.loc[fs:fe]
            positions_fold = positions_df.loc[fs:fe]
            eq, m = run_portfolio_backtest(
                positions_fold, prices_fold, capital=20_000.0, cost_bps=args.cost_bps,
            )
            m["fold"]  = i
            m["start"] = fs
            m["end"]   = fe
            fold_metrics.append(m)
            equity_pieces.append(eq)
            print(f"  Fold {i} ({fs.date()} to {fe.date()}): "
                  f"{m['total_return']:.1%} return  |  Sharpe {m['sharpe']:.2f}")

        stitched = pd.concat(equity_pieces)
        stitched = stitched[~stitched.index.duplicated(keep="first")]
        overall  = _compute_metrics(stitched, float(stitched["equity"].iloc[0]))
        overall["start"] = fold_starts[0]
        overall["end"]   = fold_ends[-1]

        total_ret    = (stitched["equity"].iloc[-1] / stitched["equity"].iloc[0]) - 1
        print(f"\nWalk-Forward ({len(fold_starts)} folds): "
              f"{total_ret:.1%} return  |  "
              f"Sharpe {overall['sharpe']:.2f}  |  "
              f"Max DD {overall['max_drawdown']:.1%}")

        print("Opening windows...")
        _show(plot_pca_walk_forward(stitched, fold_metrics, overall, params),
              f"PCA — {universe_label} — Walk-Forward")
        return

    # ── Train/test split ──────────────────────────────────────────────────────
    split_date  = None
    test_period = args.test_period
    if test_period:
        n_test = _PERIOD_BARS.get(test_period, 252)
        if n_test >= len(returns_df) - window - 10:
            print(f"WARNING: --test-period '{test_period}' leaves too little training data. Ignoring.")
            test_period = None
        else:
            split_idx  = len(returns_df) - n_test
            split_date = returns_df.index[split_idx]
            print(f"Train/test split — training up to {split_date.date()}  |  test: {test_period} forward")

    print(f"Computing rolling PCA residuals (window={window}, k={args.n_factors})...")
    residuals_df = rolling_pca_residuals(returns_df, window=window, n_components=args.n_factors)

    print(f"Generating signals (z_entry={args.z_entry}, top_n={args.top_n})...")
    positions_df, z_scores_df = generate_pca_signals(
        residuals_df, window=window,
        z_entry=args.z_entry, z_exit=args.z_exit, z_stop=args.z_stop,
        top_n=args.top_n,
    )

    # Restrict backtest to test window if set
    if split_date is not None:
        prices_bt    = prices_df.loc[prices_df.index >= split_date]
        positions_bt = positions_df.loc[positions_df.index >= split_date]
        print(f"Backtesting on test period ({split_date.date()} to {prices_bt.index[-1].date()})")
    else:
        prices_bt, positions_bt = prices_df, positions_df

    print(f"Running portfolio backtest (cost={args.cost_bps}bps)...")
    equity_curve, bt_metrics = run_portfolio_backtest(
        positions_bt, prices_bt, capital=20_000.0, cost_bps=args.cost_bps,
    )

    period_label = f"({test_period} test)" if test_period else ""
    print(
        f"PCA Stat Arb {period_label}: "
        f"{bt_metrics['total_return']:.1%} return  |  "
        f"Sharpe {bt_metrics['sharpe']:.2f}  |  "
        f"Max DD {bt_metrics['max_drawdown']:.1%}"
    )

    params["test_period"] = test_period

    print("Opening windows...")
    _show(plot_pca_equity(equity_curve, bt_metrics, universe_label, params),
          f"PCA — {universe_label} — Equity")
    _show(plot_pca_zscore_heatmap(z_scores_df, positions_df, universe_label, params),
          f"PCA — {universe_label} — Z-Scores")
    _show(plot_pca_positions(positions_df, universe_label),
          f"PCA — {universe_label} — Positions")


def _register_pca(subparsers):
    parser = subparsers.add_parser("pca", help="PCA statistical arbitrage")
    parser.add_argument("--universe", required=True, metavar="NAME",
                        help=f"Named universe from config. Options: {', '.join(SCAN_UNIVERSES)}")
    parser.add_argument("--period",    default="2y",  help="Data lookback (default: 2y)")
    parser.add_argument("--walk-forward", default=None, type=int, metavar="N",
                        dest="walk_forward",
                        help="Run N non-overlapping 1-year OOS folds (overrides --test-period)")
    parser.add_argument("--window",    default=60, type=int,
                        help="Rolling window for PCA and z-scoring (default: 60)")
    parser.add_argument("--n-factors", default=3,  type=int, metavar="K",
                        help="Number of PCA factors to extract (default: 3)")
    parser.add_argument("--top-n",     default=3,  type=int, metavar="N",
                        help="Max simultaneous positions per side, long and short (default: 3)")
    parser.add_argument("--z-entry",   default=2.0, type=float,
                        help="Entry threshold (default: 2.0)")
    parser.add_argument("--z-exit",    default=0.5, type=float,
                        help="Exit threshold (default: 0.5)")
    parser.add_argument("--z-stop",    default=3.0, type=float,
                        help="Stop-loss threshold (default: 3.0)")
    parser.add_argument("--cost-bps",  default=5.0, type=float, metavar="BPS",
                        help="Round-trip transaction cost in basis points (default: 5)")
    parser.add_argument("--test-period", default=None, metavar="PERIOD",
                        choices=["3mo", "6mo", "1y", "2y"],
                        help="Hold out the most recent PERIOD as out-of-sample test window.")
    parser.add_argument("--data-provider", default="yfinance", metavar="PROVIDER",
                        choices=["yfinance", "alpaca"], dest="data_provider",
                        help="Price data source: yfinance (default) or alpaca")
    parser.set_defaults(func=_run_pca)


def _run_basket_dynamic(args):
    """
    Basket backtest with time-varying constituents from EDGAR N-PORT.

    Resolves the ETF's top-N holdings into stable segments, swapping stocks
    in/out at each historical change. Each segment is backtested independently
    (positions forced flat at boundaries) and the equity curves are stitched.
    For dates before N-PORT coverage (~mid-2019), --stocks is used as fallback.
    """
    from src.data.fetcher import fetch_price, fetch_prices_bulk
    from src.data.edgar import get_constituent_segments
    from src.analytics.basket import rolling_basket_spread
    from src.strategies.basket.signals import generate_basket_signals
    from src.strategies.basket.backtest import run_basket_backtest
    from src.strategies.basket.viz import plot_basket_spread, plot_basket_trade_pnl
    from src.strategies.pairs.viz import plot_equity_curve, plot_backtest_metrics
    from src.backtest.metrics import compute_metrics

    etf           = args.etf.upper()
    period        = args.period
    window        = args.window
    top_n         = getattr(args, "top_n", 5)
    max_hold_days = getattr(args, "max_hold_days", 0)
    vix_filter    = getattr(args, "vix_filter", 0.0)
    vol_target    = getattr(args, "vol_target", 0.0)
    fallback      = [s.strip().upper() for s in args.stocks] if args.stocks else None
    capital       = 20_000.0

    print(f"Fetching {etf} price history ({period})...")
    etf_prices = fetch_price(etf, period=period)
    start, end = etf_prices.index[0], etf_prices.index[-1]

    print(f"Resolving EDGAR top-{top_n} constituent segments for {etf}...")
    segments = get_constituent_segments(etf, start, end, top_n=top_n,
                                        fallback_stocks=fallback)
    if not segments:
        print("ERROR: No constituent segments resolved and no --stocks fallback.")
        sys.exit(1)

    # Normalize share-class tickers for yfinance (BRK/B -> BRK-B)
    segments = [
        (s_start, s_end, [s.replace("/", "-") for s in stx])
        for s_start, s_end, stx in segments
    ]

    print(f"\n{len(segments)} constituent segment(s):")
    for s_start, s_end, stx in segments:
        print(f"  {s_start.date()} -> {s_end.date()}: [{', '.join(stx)}]")

    # Fetch all stocks used across every segment in one bulk call
    all_stocks = sorted({s for _, _, stx in segments for s in stx})
    print(f"\nFetching {len(all_stocks)} unique constituent(s)...")
    prices = fetch_prices_bulk(all_stocks, period=period)

    vix_series = None
    if vix_filter > 0:
        try:
            vix_series = fetch_price("^VIX", period=period)
            print(f"VIX filter active (threshold: {vix_filter}).")
        except Exception:
            print("WARNING: Could not fetch VIX — filter disabled.")

    # Backtest each segment independently, stitch equity and trades
    running_capital = capital
    all_trades      = []
    equity_pieces   = []
    spread_pieces   = []
    zscore_pieces   = []
    signal_pieces   = []
    boundaries      = []

    for s_start, s_end, stx in segments:
        avail = [s for s in stx if s in prices]
        if len(avail) < 2:
            print(f"  Skipping segment {s_start.date()} — <2 stocks available.")
            continue

        cdf = pd.DataFrame({s: prices[s] for s in avail}).dropna()
        ea  = etf_prices.reindex(cdf.index).dropna()
        cdf = cdf.reindex(ea.index)

        # Full-period rolling spread for proper warmup, then slice to the segment
        full_spread = rolling_basket_spread(ea, cdf, window=window)
        sig_full, z_full = generate_basket_signals(
            full_spread, window=window,
            z_entry=args.z_entry, z_exit=args.z_exit, z_stop=args.z_stop,
            vix_series=vix_series, vix_threshold=vix_filter,
        )

        mask = (full_spread.index >= s_start) & (full_spread.index <= s_end)
        seg_spread  = full_spread[mask]
        seg_zscore  = z_full[mask]
        seg_signals = sig_full[mask]

        if seg_spread.dropna().empty:
            continue

        t, eq, _ = run_basket_backtest(
            seg_signals, seg_spread, capital=running_capital,
            cost_bps=args.cost_bps, n_stocks=len(avail),
            max_hold_days=max_hold_days, vol_target=vol_target,
        )
        if not t.empty:
            t = t.copy()
            t["segment"] = f"{s_start.date()}:{','.join(avail)}"
            all_trades.append(t)
        equity_pieces.append(eq)
        spread_pieces.append(seg_spread)
        zscore_pieces.append(seg_zscore)
        signal_pieces.append(seg_signals)
        boundaries.append(s_end)
        if not eq.empty:
            running_capital = float(eq["equity"].iloc[-1])

    if not equity_pieces:
        print("ERROR: No segments produced a backtest.")
        sys.exit(1)

    equity_curve = pd.concat(equity_pieces)
    equity_curve = equity_curve[~equity_curve.index.duplicated(keep="last")]
    spread       = pd.concat(spread_pieces)
    spread       = spread[~spread.index.duplicated(keep="last")]
    zscore       = pd.concat(zscore_pieces)
    zscore       = zscore[~zscore.index.duplicated(keep="last")]
    signals      = pd.concat(signal_pieces)
    signals      = signals[~signals.index.duplicated(keep="last")]
    trades       = pd.concat(all_trades) if all_trades else pd.DataFrame()

    bt_metrics = compute_metrics(equity_curve, trades, capital)

    print(
        f"\nDynamic basket: {bt_metrics['n_trades']} trades  |  "
        f"{bt_metrics['total_return']:.1%} return  |  "
        f"Sharpe {bt_metrics['sharpe']:.2f}  |  "
        f"Max DD {bt_metrics['max_drawdown']:.1%}"
    )

    # Latest segment's stock list drives the price-chart basket label
    latest_stocks = segments[-1][2]
    basket_prices = (etf_prices.reindex(spread.index) * np.exp(-spread)).dropna()
    etf_aligned   = etf_prices.reindex(spread.index)

    params = {
        "period": period, "window": window,
        "z_entry": args.z_entry, "z_exit": args.z_exit, "z_stop": args.z_stop,
    }

    walk_forward = getattr(args, "walk_forward", None)
    if walk_forward == -1:
        period_years = {"1y": 1, "2y": 2, "3y": 3, "5y": 5, "10y": 10}.get(period, 5)
        walk_forward = max(1, period_years - 1)

    if walk_forward:
        from src.backtest.metrics import compute_metrics as _cm
        from src.strategies.basket.viz import plot_walk_forward_results
        fold_bars = 252
        T = len(signals)
        fold_results, all_fold_trades, equity_pieces_wf = [], [], []
        running_capital_wf = capital

        for i in range(walk_forward):
            start_idx = T - (walk_forward - i) * fold_bars
            end_idx   = min(T - (walk_forward - i - 1) * fold_bars, T) - 1
            if start_idx < window + 10:
                continue
            fs = signals.index[start_idx]
            fe = signals.index[end_idx]
            t, eq, m = run_basket_backtest(
                signals.loc[fs:fe], spread.loc[fs:fe],
                capital=running_capital_wf, cost_bps=args.cost_bps,
                n_stocks=top_n, max_hold_days=max_hold_days, vol_target=vol_target,
            )
            fold_results.append({
                "fold": i + 1, "start": fs, "end": fe,
                **{k: m[k] for k in ("n_trades", "total_return", "sharpe",
                                     "sortino", "max_drawdown", "win_rate")},
            })
            all_fold_trades.append(t)
            equity_pieces_wf.append(eq)
            running_capital_wf = float(eq["equity"].iloc[-1])
            print(f"  Fold {i+1} ({fs.date()} to {fe.date()}): "
                  f"{m['n_trades']} trades  |  "
                  f"{m['total_return']:.1%} return  |  "
                  f"Sharpe {m['sharpe']:.2f}")

        if not fold_results:
            print("Not enough data for walk-forward folds.")
            return

        stitched_wf = pd.concat(equity_pieces_wf)
        overall_wf  = _cm(
            stitched_wf,
            pd.concat(all_fold_trades) if any(not t.empty for t in all_fold_trades) else pd.DataFrame(),
            capital,
        )
        n_total     = sum(r["n_trades"] for r in fold_results)
        mean_ret    = sum(r["total_return"] for r in fold_results) / len(fold_results)
        mean_sharpe = sum(r["sharpe"] for r in fold_results) / len(fold_results)
        print(f"\nWalk-Forward ({len(fold_results)} folds): "
              f"{n_total} total trades  |  "
              f"{mean_ret:.1%} avg fold return  |  "
              f"Sharpe {mean_sharpe:.2f} avg")
        _show(
            plot_walk_forward_results(stitched_wf, fold_results, overall_wf,
                                      {**params, "cost_bps": args.cost_bps}),
            f"Basket (dynamic) — {etf} — Walk-Forward Summary",
        )
        return

    print("Opening windows...")
    _show(
        plot_basket_spread(spread, zscore, signals, etf, latest_stocks, params,
                           etf_prices=etf_aligned, basket_prices=basket_prices),
        f"Basket (dynamic) — {etf} — Spread",
    )
    if not trades.empty:
        _show(plot_equity_curve(equity_curve, trades, etf, "BASKET", capital),
              f"Basket (dynamic) — {etf} — Equity")
        # Per-leg P&L breakdown
        etf_at_entry = etf_aligned.reindex(trades["entry_date"]).values
        etf_at_exit  = etf_aligned.reindex(trades["exit_date"]).values
        bsk_at_entry = basket_prices.reindex(trades["entry_date"]).values
        bsk_at_exit  = basket_prices.reindex(trades["exit_date"]).values
        etf_log_ret  = np.log(etf_at_exit / etf_at_entry)
        bsk_log_ret  = np.log(bsk_at_exit / bsk_at_entry)
        direction    = trades["direction"].values
        notional     = trades["notional"].values
        etf_pct_arr  = direction *  etf_log_ret * notional / capital
        bsk_pct_arr  = direction * -bsk_log_ret * notional / capital
        _show(plot_basket_trade_pnl(trades, etf, etf_pct_arr, bsk_pct_arr),
              f"Basket (dynamic) — {etf} — Trade P&L")
        _show(plot_backtest_metrics(bt_metrics, trades, etf, "BASKET", params),
              f"Basket (dynamic) — {etf} — Metrics")

        if getattr(args, "monte_carlo", False):
            from src.backtest.monte_carlo import bootstrap_returns
            from src.strategies.basket.viz import plot_monte_carlo
            n_sims = getattr(args, "mc_sims", 10_000)
            print(f"Running Monte Carlo bootstrap ({n_sims:,} sims, daily returns)...")
            mc = bootstrap_returns(equity_curve, capital=capital, n_sims=n_sims)
            _print_mc_summary(mc)
            _show(plot_monte_carlo(mc, bt_metrics, etf, params),
                  f"Basket (dynamic) — {etf} — Monte Carlo")


def _run_basket(args):
    global _SAVE_IMAGES_DIR, _SAVE_FIGS_DIR
    _SAVE_IMAGES_DIR = getattr(args, "save_images", None)
    _SAVE_FIGS_DIR   = getattr(args, "save_figs",   None)

    from src.data.fetcher import fetch_price
    from src.analytics.stationarity import adf_test, compute_half_life
    from src.analytics.basket import rolling_basket_spread
    from src.strategies.basket.signals import generate_basket_signals
    from src.strategies.basket.backtest import run_basket_backtest
    from src.strategies.basket.viz import plot_basket_spread
    from src.strategies.pairs.viz import (
        plot_equity_curve, plot_trade_pnl, plot_backtest_metrics,
    )

    if not getattr(args, "static_constituents", False):
        _run_basket_dynamic(args)
        return

    if not args.stocks:
        print("ERROR: --stocks is required unless --dynamic-constituents is set.")
        sys.exit(1)

    etf      = args.etf.upper()
    stocks   = [s.strip().upper() for s in args.stocks]
    period   = args.period
    window   = args.window
    provider = getattr(args, "data_provider", "yfinance")

    print(f"Fetching {etf} + {len(stocks)} constituent(s) ({period}) via {provider}...")
    if provider == "alpaca":
        from src.data.fetcher import fetch_prices_bulk
        all_tickers = [etf] + stocks
        bulk = fetch_prices_bulk(all_tickers, period=period, provider="alpaca")
        if etf not in bulk:
            print(f"ERROR fetching {etf} from Alpaca.")
            sys.exit(1)
        etf_prices  = bulk[etf]
        prices_dict = {s: bulk[s] for s in stocks if s in bulk}
        missing = [s for s in stocks if s not in bulk]
        if missing:
            print(f"  WARNING: Could not fetch {missing}, skipping.")
    else:
        try:
            etf_prices = fetch_price(etf, period=period)
        except Exception as e:
            print(f"ERROR fetching {etf}: {e}")
            sys.exit(1)
        prices_dict = {}
        for s in stocks:
            try:
                prices_dict[s] = fetch_price(s, period=period)
            except Exception:
                print(f"  WARNING: Could not fetch {s}, skipping.")

    if len(prices_dict) < 2:
        print("ERROR: Need at least 2 constituent tickers with data.")
        sys.exit(1)

    constituent_prices = pd.DataFrame(prices_dict).dropna()
    etf_aligned        = etf_prices.reindex(constituent_prices.index).dropna()
    constituent_prices = constituent_prices.reindex(etf_aligned.index)
    print(f"  {len(etf_aligned)} aligned bars, {constituent_prices.shape[1]} constituents.")

    walk_forward  = getattr(args, "walk_forward",  None)
    if walk_forward == -1:
        period_years = {"1y": 1, "2y": 2, "3y": 3, "5y": 5, "10y": 10}.get(period, 5)
        walk_forward = max(1, period_years - 1)
    max_hold_days = getattr(args, "max_hold_days", 0)
    vix_filter    = getattr(args, "vix_filter",    0.0)
    vol_target    = getattr(args, "vol_target",    0.0)

    print(f"Computing rolling basket spread (window={window})...")
    spread = rolling_basket_spread(etf_aligned, constituent_prices, window=window)

    adf = adf_test(spread.dropna())
    hl  = compute_half_life(spread.dropna())
    hl_str = f"{hl:.1f} days" if hl != float("inf") else "inf"
    print(
        f"Spread ADF p-val: {adf['p_value']:.4f}  "
        f"({'stationary' if adf['is_stationary'] else 'non-stationary'})  "
        f"Half-life: {hl_str}"
    )

    vix_series = None
    if vix_filter > 0:
        try:
            vix_series = fetch_price("^VIX", period=period)
            print(f"VIX filter active (threshold: {vix_filter}).")
        except Exception:
            print("WARNING: Could not fetch VIX — filter disabled.")

    print("Generating signals...")
    signals, zscore = generate_basket_signals(
        spread, window=window,
        z_entry=args.z_entry, z_exit=args.z_exit, z_stop=args.z_stop,
        vix_series=vix_series, vix_threshold=vix_filter,
    )

    params = {
        "period": period, "window": window,
        "z_entry": args.z_entry, "z_exit": args.z_exit, "z_stop": args.z_stop,
    }

    # ── Walk-forward mode ─────────────────────────────────────────────────────
    if walk_forward:
        from src.backtest.metrics import compute_metrics
        from src.strategies.basket.viz import plot_walk_forward_results
        fold_bars = 252
        T = len(signals)
        fold_results  = []
        all_trades    = []
        equity_pieces = []
        running_capital = 20_000.0

        for i in range(walk_forward):
            start_idx = T - (walk_forward - i) * fold_bars
            end_idx   = min(T - (walk_forward - i - 1) * fold_bars, T) - 1
            if start_idx < window + 10:
                continue
            fs = signals.index[start_idx]
            fe = signals.index[end_idx]
            t, eq, m = run_basket_backtest(
                signals.loc[fs:fe], spread.loc[fs:fe],
                capital=running_capital, cost_bps=args.cost_bps,
                max_hold_days=max_hold_days, vol_target=vol_target,
            )
            fold_results.append({
                "fold": i + 1, "start": fs, "end": fe,
                **{k: m[k] for k in ("n_trades", "total_return", "sharpe", "sortino",
                                     "max_drawdown", "win_rate")},
            })
            all_trades.append(t)
            equity_pieces.append(eq)
            running_capital = float(eq["equity"].iloc[-1])
            print(f"  Fold {i+1} ({fs.date()} to {fe.date()}): "
                  f"{m['n_trades']} trades  |  "
                  f"{m['total_return']:.1%} return  |  "
                  f"Sharpe {m['sharpe']:.2f}")

        if not fold_results:
            print("Not enough data for walk-forward folds.")
            return

        stitched = pd.concat(equity_pieces)
        overall  = compute_metrics(stitched, pd.concat(all_trades) if any(not t.empty for t in all_trades) else pd.DataFrame(), 20_000.0)
        n_total     = sum(r["n_trades"] for r in fold_results)
        mean_ret    = sum(r["total_return"] for r in fold_results) / len(fold_results)
        mean_sharpe = sum(r["sharpe"] for r in fold_results) / len(fold_results)
        print(f"\nWalk-Forward ({len(fold_results)} folds): "
              f"{n_total} total trades  |  "
              f"{mean_ret:.1%} avg fold return  |  "
              f"Sharpe {mean_sharpe:.2f} avg")

        _show(
            plot_walk_forward_results(stitched, fold_results, overall, {**params, "cost_bps": args.cost_bps}),
            f"Basket — {etf} — Walk-Forward Summary",
        )
        return

    # ── Train/test split (single backtest) ────────────────────────────────────
    split_date  = None
    test_period = args.test_period
    if test_period:
        n_test = _PERIOD_BARS.get(test_period, 252)
        if n_test >= len(etf_aligned) - window - 10:
            print(f"WARNING: --test-period '{test_period}' leaves too little data. Ignoring.")
            test_period = None
        else:
            split_idx  = len(etf_aligned) - n_test
            split_date = etf_aligned.index[split_idx]
            print(f"Train/test split — training up to {split_date.date()}  |  test: {test_period}")

    if split_date is not None:
        signals_bt = signals.loc[signals.index >= split_date]
        spread_bt  = spread.loc[spread.index >= split_date]
        print(f"Backtesting on test period ({split_date.date()} to {signals.index[-1].date()})")
    else:
        signals_bt, spread_bt = signals, spread

    print("Running backtest...")
    trades, equity_curve, bt_metrics = run_basket_backtest(
        signals_bt, spread_bt, capital=20_000.0, cost_bps=args.cost_bps,
        max_hold_days=max_hold_days, vol_target=vol_target,
    )

    period_label = f"({test_period} test)" if test_period else ""
    print(
        f"Basket {period_label}: {bt_metrics['n_trades']} trades  |  "
        f"{bt_metrics['total_return']:.1%} return  |  "
        f"Sharpe {bt_metrics['sharpe']:.2f}"
    )

    # Weighted basket price: exp(log(etf) - spread) = etf * exp(-spread)
    basket_prices = (etf_aligned * np.exp(-spread)).dropna()

    print("Opening windows...")
    _show(
        plot_basket_spread(
            spread, zscore, signals, etf, stocks, params,
            split_date=split_date,
            etf_prices=etf_aligned,
            basket_prices=basket_prices,
        ),
        f"Basket — {etf} — Spread",
    )
    if not trades.empty:
        _show(plot_equity_curve(equity_curve, trades, etf, "BASKET", 20_000.0),
              f"Basket — {etf} — Equity")

        # Per-leg P&L breakdown: ETF leg and basket leg contributions
        from src.strategies.basket.viz import plot_basket_trade_pnl
        etf_at_entry    = etf_aligned.reindex(trades["entry_date"]).values
        etf_at_exit     = etf_aligned.reindex(trades["exit_date"]).values
        basket_at_entry = basket_prices.reindex(trades["entry_date"]).values
        basket_at_exit  = basket_prices.reindex(trades["exit_date"]).values
        etf_log_ret     = np.log(etf_at_exit / etf_at_entry)
        basket_log_ret  = np.log(basket_at_exit / basket_at_entry)
        direction       = trades["direction"].values
        notional        = trades["notional"].values
        etf_pct_arr     = direction *  etf_log_ret    * notional / 20_000.0
        basket_pct_arr  = direction * -basket_log_ret * notional / 20_000.0
        _show(plot_basket_trade_pnl(trades, etf, etf_pct_arr, basket_pct_arr),
              f"Basket — {etf} — Trade P&L")
        _show(plot_backtest_metrics(bt_metrics, trades, etf, "BASKET", params),
              f"Basket — {etf} — Metrics")

        if getattr(args, "monte_carlo", False):
            from src.backtest.monte_carlo import bootstrap_returns
            from src.strategies.basket.viz import plot_monte_carlo
            n_sims = getattr(args, "mc_sims", 10_000)
            print(f"Running Monte Carlo bootstrap ({n_sims:,} sims, daily returns)...")
            mc = bootstrap_returns(equity_curve, capital=20_000.0, n_sims=n_sims)
            _print_mc_summary(mc)
            _show(plot_monte_carlo(mc, bt_metrics, etf, params),
                  f"Basket — {etf} — Monte Carlo")


def _run_basket_multi(args):
    global _SAVE_IMAGES_DIR, _SAVE_FIGS_DIR
    _SAVE_IMAGES_DIR = getattr(args, "save_images", None)
    _SAVE_FIGS_DIR   = getattr(args, "save_figs",   None)

    import math as _math
    from src.data.fetcher import fetch_price
    from src.analytics.stationarity import adf_test, compute_half_life
    from src.analytics.basket import rolling_basket_spread
    from src.strategies.basket.signals import generate_basket_signals
    from src.strategies.basket.backtest import run_basket_backtest
    from src.strategies.basket.viz import plot_basket_combined, plot_basket_legs, plot_walk_forward_results
    from src.backtest.portfolio_engine import _compute_metrics

    # Parse "--basket ETF:S1,S2,S3" entries
    baskets = []
    for spec in args.baskets:
        if ":" not in spec:
            print(f"ERROR: --basket must be 'ETF:S1,S2,...' -- got '{spec}'")
            sys.exit(1)
        etf_part, stocks_part = spec.split(":", 1)
        stocks = [s.strip().upper() for s in stocks_part.split(",") if s.strip()]
        baskets.append((etf_part.strip().upper(), stocks))

    period        = args.period
    window        = args.window
    test_period   = args.test_period
    n_folds       = getattr(args, "walk_forward",  None)
    max_hold_days = getattr(args, "max_hold_days", 0)
    vix_filter    = getattr(args, "vix_filter",    0.0)
    vol_target    = getattr(args, "vol_target",    0.0)
    total_capital = 20_000.0
    leg_capital   = total_capital / len(baskets)

    period_years = {"1y": 1, "2y": 2, "3y": 3, "5y": 5, "10y": 10}.get(period, 5)
    if n_folds == -1:  # --walk-forward given without a count → auto from period
        n_folds = max(1, period_years - 1)

    params = {
        "period": period, "window": window,
        "z_entry": args.z_entry, "z_exit": args.z_exit, "z_stop": args.z_stop,
        "cost_bps": args.cost_bps, "test_period": test_period,
    }

    dynamic_constituents = not getattr(args, "static_constituents", False)
    top_n = getattr(args, "top_n", 5)

    vix_series = None
    if vix_filter > 0:
        try:
            vix_series = fetch_price("^VIX", period=period)
            print(f"VIX filter active (threshold: {vix_filter}).")
        except Exception:
            print("WARNING: Could not fetch VIX — filter disabled.")

    # ---- Dynamic constituent mode (EDGAR N-PORT) --------------------------------
    if dynamic_constituents:
        from src.data.fetcher import fetch_prices_bulk
        from src.data.edgar import get_constituent_segments
        from src.strategies.basket.backtest import run_basket_backtest_segmented

        period_years = {"1y": 1, "2y": 2, "3y": 3, "5y": 5, "10y": 10}.get(period, 5)
        full_end   = pd.Timestamp.today().normalize()
        full_start = full_end - pd.DateOffset(years=period_years)
        grace_days = max(max_hold_days, 30)

        print("\nUsing EDGAR N-PORT historical constituents (survivorship-bias corrected).")

        # Step 1: resolve constituent segments per ETF
        # For pre-EDGAR dates (before ~April 2019), use the earliest available
        # N-PORT filing's top-N as the fallback rather than today's composition.
        raw_segments = {}
        all_seg_tickers: set = set()
        etf_tickers = [etf for etf, _ in baskets]
        for etf, fallback_stocks in baskets:
            print(f"  Resolving segments for {etf}...")
            # Get segments without any pre-EDGAR fallback first
            segs = get_constituent_segments(etf, full_start, full_end, top_n=top_n,
                                            fallback_stocks=None)
            if segs:
                # If EDGAR doesn't cover the full start, prepend a segment using
                # the earliest available filing's stocks (not today's stocks)
                first_seg_start = segs[0][0]
                if first_seg_start > full_start:
                    earliest_stocks = segs[0][2][:top_n]
                    pre_seg = (full_start, first_seg_start - pd.Timedelta(days=1), earliest_stocks)
                    segs = [pre_seg] + list(segs)
                    print(f"    Pre-EDGAR ({full_start.date()} to {pre_seg[1].date()}): "
                          f"using earliest filing stocks [{', '.join(earliest_stocks)}]")
            else:
                # EDGAR completely unavailable — fall back to CLI stocks
                fb = [s.replace("/", "-") for s in fallback_stocks] if fallback_stocks else []
                segs = [(full_start, full_end, fb)]
            segs = [(s, e, [t.replace("/", "-") for t in stx]) for s, e, stx in segs]
            raw_segments[etf] = segs
            for _, _, stx in segs:
                all_seg_tickers.update(stx)

        # Step 2: bulk-fetch all prices
        all_tickers = list((all_seg_tickers | set(etf_tickers)) - {""})
        print(f"  Fetching {len(all_tickers)} unique tickers ({period})...")
        all_prices = fetch_prices_bulk(all_tickers, period=period)

        # Step 3: compute spread + signals per segment (with backward warmup and forward grace)
        etf_seg_data: dict = {}
        for etf, segs in raw_segments.items():
            etf_px = all_prices.get(etf)
            if etf_px is None:
                print(f"  ERROR: no prices for {etf}, skipping.")
                continue
            etf_seg_data[etf] = []
            for seg_start, seg_end, seg_stocks in segs:
                avail = [s for s in seg_stocks if s in all_prices and s != etf]
                if len(avail) < 2:
                    continue
                compute_start = max(etf_px.index[0],
                                    seg_start - pd.Timedelta(days=int(window * 1.5)))
                compute_end   = min(etf_px.index[-1],
                                    seg_end   + pd.Timedelta(days=grace_days + 10))
                cdf = pd.DataFrame({s: all_prices[s] for s in avail}).dropna()
                ea  = etf_px.reindex(cdf.index).dropna()
                cdf = cdf.reindex(ea.index)
                cdf = cdf.loc[(cdf.index >= compute_start) & (cdf.index <= compute_end)]
                ea  = ea.reindex(cdf.index).dropna()
                cdf = cdf.reindex(ea.index)
                if len(ea) < window + 10:
                    continue
                spread_full = rolling_basket_spread(
                    ea, cdf, window=window,
                    ridge_alpha=args.ridge_alpha, regime_filter=args.regime_filter,
                )
                signals_full, _ = generate_basket_signals(
                    spread_full, window=window,
                    z_entry=args.z_entry, z_exit=args.z_exit, z_stop=args.z_stop,
                    vix_series=vix_series, vix_threshold=vix_filter,
                )
                etf_seg_data[etf].append((seg_start, seg_end, signals_full, spread_full, avail))

            if not etf_seg_data.get(etf):
                print(f"  WARNING: no valid segments computed for {etf}.")

        if not etf_seg_data:
            print("ERROR: No ETFs produced valid segment data.")
            sys.exit(1)

        for etf, segs in etf_seg_data.items():
            print(f"\n  {etf}: {len(segs)} segment(s)")
            for ss, se, _, _, stx in segs:
                print(f"    {ss.date()} -> {se.date()}: [{', '.join(stx)}]")

        ref_px = next(v for v in all_prices.values() if v is not None)

        # ---- Dynamic walk-forward ------------------------------------------------
        if n_folds:
            T          = len(ref_px)
            train_bars = T // period_years
            fold_bars  = max(1, (T - train_bars) // n_folds)
            fold_label = (f"{round(fold_bars / 252)}y" if fold_bars >= 200
                          else f"{fold_bars}d")
            print(f"\nRunning dynamic walk-forward ({n_folds} folds x {fold_label})...")
            fold_combined_metrics = []
            all_stitched_pnls     = []

            for fold_k in range(n_folds):
                start_idx = T - (n_folds - fold_k) * fold_bars
                end_idx   = min(T - (n_folds - fold_k - 1) * fold_bars, T)
                if start_idx < window + 10 or end_idx - 1 >= len(ref_px.index):
                    continue
                fold_start = ref_px.index[start_idx]
                fold_end   = ref_px.index[end_idx - 1]

                fold_leg_pnls  = []
                fold_n_trades  = 0
                fold_win_rates = []

                for etf, _ in baskets:
                    segs = etf_seg_data.get(etf)
                    if not segs:
                        continue
                    fold_segs = []
                    for ss, se, sigs, sprd, stx in segs:
                        if se < fold_start or ss > fold_end:
                            continue
                        eff_s = max(ss, fold_start)
                        eff_e = min(se, fold_end)
                        sl = sigs.loc[(sigs.index >= eff_s) & (sigs.index <= eff_e)]
                        if sl.empty:
                            continue
                        fold_segs.append((eff_s, eff_e, sl, sprd))
                    if not fold_segs:
                        continue

                    n_sl = len(segs[-1][4]) if segs else 1
                    t_fold, eq_fold, mf = run_basket_backtest_segmented(
                        fold_segs, capital=leg_capital,
                        cost_bps=args.cost_bps, n_stocks=n_sl,
                        max_hold_days=max_hold_days, vol_target=vol_target,
                    )
                    fold_n_trades += mf.get("n_trades", 0)
                    wr = mf.get("win_rate")
                    if wr is not None and not (isinstance(wr, float) and _math.isnan(wr)):
                        fold_win_rates.append(wr)
                    if not t_fold.empty:
                        fold_leg_pnls.append(eq_fold["equity"].diff().fillna(0).rename(etf))

                if not fold_leg_pnls:
                    print(f"  Fold {fold_k + 1}: no legs ran, skipping.")
                    continue

                fold_pnl_df   = pd.concat(fold_leg_pnls, axis=1, sort=True).fillna(0)
                fold_comb_pnl = fold_pnl_df.sum(axis=1)
                fold_equity   = (total_capital + fold_comb_pnl.cumsum()).to_frame("equity")
                fm = _compute_metrics(fold_equity, total_capital)
                fm["n_trades"] = fold_n_trades
                fm["win_rate"] = (sum(fold_win_rates) / len(fold_win_rates)
                                  if fold_win_rates else float("nan"))
                fm["start"] = fold_start
                fm["end"]   = fold_end
                fm["fold"]  = fold_k + 1
                fold_combined_metrics.append(fm)
                all_stitched_pnls.append(fold_comb_pnl)
                print(f"  Fold {fold_k + 1} ({fm['start'].date()} to {fm['end'].date()}): "
                      f"{fm['total_return']:.1%}  |  Sharpe {fm['sharpe']:.2f}  |  "
                      f"{fold_n_trades} trades")

            if not all_stitched_pnls:
                print("ERROR: No fold data. Check period and EDGAR coverage.")
                sys.exit(1)

            full_pnl        = pd.concat(all_stitched_pnls).sort_index()
            stitched_equity = (total_capital + full_pnl.cumsum()).to_frame("equity")
            overall = _compute_metrics(stitched_equity, total_capital)
            overall["n_trades"] = sum(fm["n_trades"] for fm in fold_combined_metrics)
            all_wrs = [fm["win_rate"] for fm in fold_combined_metrics
                       if not (isinstance(fm["win_rate"], float) and _math.isnan(fm["win_rate"]))]
            overall["win_rate"] = sum(all_wrs) / len(all_wrs) if all_wrs else float("nan")
            overall["start"]    = stitched_equity.index[0]
            overall["end"]      = stitched_equity.index[-1]
            print(
                f"\nDynamic Walk-Forward ({n_folds} folds): "
                f"{overall['total_return']:.1%} return  |  "
                f"Sharpe {overall['sharpe']:.2f}  |  "
                f"Max DD {overall['max_drawdown']:.1%}  |  "
                f"{overall['n_trades']} trades total"
            )
            print("Opening windows...")
            _show(
                plot_walk_forward_results(stitched_equity, fold_combined_metrics, overall, params),
                "Basket (dynamic) — Walk-Forward",
            )
            return

        # ---- Dynamic OOS ---------------------------------------------------------
        from src.strategies.basket.viz import plot_basket_combined, plot_basket_legs

        leg_equities: dict = {}
        leg_metrics:  dict = {}
        daily_pnls:   list = []

        for etf, _ in baskets:
            segs = etf_seg_data.get(etf)
            if not segs:
                continue
            # Strip stocks (5th element) — backtest function takes 4-tuples
            oos_segs = [(ss, se, sigs, sprd) for ss, se, sigs, sprd, *_ in segs]
            if test_period:
                n_test = _PERIOD_BARS.get(test_period, 252)
                etf_px = all_prices.get(etf)
                if etf_px is not None and len(etf_px) > n_test:
                    split_date = etf_px.index[-n_test]
                    oos_segs = []
                    for ss, se, sigs, sprd, *_ in segs:
                        if se < split_date:
                            continue
                        eff_s = max(ss, split_date)
                        sl = sigs.loc[(sigs.index >= eff_s) & (sigs.index <= se)]
                        oos_segs.append((eff_s, se, sl, sprd))
            if not oos_segs:
                continue
            n_sl = len(segs[-1][4]) if segs else 1
            trades, equity_curve, metrics = run_basket_backtest_segmented(
                oos_segs, capital=leg_capital,
                cost_bps=args.cost_bps, n_stocks=n_sl,
                max_hold_days=max_hold_days, vol_target=vol_target,
            )
            print(f"  {etf}: {metrics.get('n_trades', 0)} trades  |  "
                  f"{metrics.get('total_return', 0):.1%} return  |  "
                  f"Sharpe {metrics.get('sharpe', 0):.2f}")
            leg_equities[etf] = equity_curve
            leg_metrics[etf]  = metrics
            daily_pnls.append(equity_curve["equity"].diff().fillna(0).rename(etf))

        if not leg_equities:
            print("ERROR: No baskets ran successfully.")
            sys.exit(1)

        pnl_df          = pd.concat(daily_pnls, axis=1, sort=True).fillna(0)
        combined_pnl    = pnl_df.sum(axis=1)
        combined_equity = (total_capital + combined_pnl.cumsum()).rename("equity").to_frame()
        combined_equity.index.name = "date"
        combined_metrics = _compute_metrics(combined_equity, total_capital)
        combined_metrics["n_trades"] = sum(m.get("n_trades", 0) for m in leg_metrics.values())

        period_label = f"({test_period} OOS)" if test_period else f"({period} full)"
        print(f"\nCombined portfolio {period_label}: "
              f"{combined_metrics['total_return']:.1%} return  |  "
              f"Sharpe {combined_metrics['sharpe']:.2f}  |  "
              f"Max DD {combined_metrics['max_drawdown']:.1%}")

        if getattr(args, "factor_analysis", False):
            from src.analytics.fama_french import (
                fetch_ff5_factors, align_returns, run_ff5_regression,
                rolling_ff5_loadings, annual_attribution,
            )
            from src.strategies.basket.viz_ff5 import plot_ff5_analysis
            ff5            = fetch_ff5_factors()
            excess_ret, factors_aligned = align_returns(combined_equity, ff5)
            result         = run_ff5_regression(excess_ret, factors_aligned)
            rolling_betas  = rolling_ff5_loadings(excess_ret, factors_aligned)
            annual_attr    = annual_attribution(rolling_betas, factors_aligned)
            alpha_ann      = result.params["const"] * 252
            print(f"  alpha={alpha_ann:.2%}/yr  R2={result.rsquared:.3f}"
                  f"  Mkt-beta={result.params['Mkt-RF']:.3f}")
            _show(plot_ff5_analysis(result, rolling_betas, annual_attr, period, params),
                  "Basket (dynamic) — FF5 Analysis")
            return

        for lbl in list(leg_equities):
            eq = (leg_equities[lbl]["equity"]
                  .reindex(combined_equity.index).ffill().fillna(leg_capital))
            leg_equities[lbl] = eq.to_frame("equity")

        print("Opening windows...")
        _show(plot_basket_combined(combined_equity, combined_metrics,
                                   list(leg_equities.keys()), params),
              "Basket Portfolio (dynamic) — Combined")
        _show(plot_basket_legs(leg_equities, leg_metrics, params),
              "Basket Portfolio (dynamic) — Individual ETFs")

        if getattr(args, "monte_carlo", False):
            from src.backtest.monte_carlo import bootstrap_returns
            from src.strategies.basket.viz import plot_monte_carlo
            n_sims = getattr(args, "mc_sims", 10_000)
            print(f"Running Monte Carlo bootstrap ({n_sims:,} sims, daily-returns)...")
            mc = bootstrap_returns(combined_equity, capital=total_capital, n_sims=n_sims)
            _print_mc_summary(mc)
            _show(plot_monte_carlo(mc, combined_metrics, "Portfolio (dynamic)", params),
                  "Basket Portfolio (dynamic) — Monte Carlo")
        return

    print(
        "\nNOTE: constituents are fixed at today's composition. "
        "Survivorship bias may inflate returns — stocks that were delisted or "
        "removed from the ETF during the backtest period are excluded."
    )

    # ---- Phase 1: Fetch data and compute signals for all baskets ----
    basket_data = []  # (label, spread, signals, n_stocks, etf_aligned, stocks)

    for etf, stocks in baskets:
        label = etf
        print(f"\nFetching {etf} + {len(stocks)} constituent(s) ({period})...")
        try:
            etf_prices = fetch_price(etf, period=period)
        except Exception as e:
            print(f"  ERROR fetching {etf}: {e}")
            continue

        prices_dict = {}
        for s in stocks:
            try:
                prices_dict[s] = fetch_price(s, period=period)
            except Exception:
                print(f"  WARNING: Could not fetch {s}, skipping.")
        if len(prices_dict) < 2:
            print(f"  ERROR: Need at least 2 constituents for {etf}. Skipping.")
            continue

        # Warn if any constituent has meaningfully less history than the ETF.
        # A short-history stock (e.g. GEV, which IPO'd 2024) will cause dropna()
        # to silently trim the entire basket to that stock's start date.
        etf_len = len(etf_prices.dropna())
        for s, px in prices_dict.items():
            stock_len = len(px.dropna())
            coverage = stock_len / etf_len if etf_len > 0 else 1.0
            if coverage < 0.85:
                missing_bars = etf_len - stock_len
                print(f"  WARNING: {s} only covers {coverage:.0%} of the {period} window "
                      f"({missing_bars} bars missing). Basket history will be trimmed to "
                      f"{px.dropna().index[0].date()} — consider replacing {s} with a "
                      f"stock that has full {period} history for static backtests.")

        constituent_prices = pd.DataFrame(prices_dict).dropna()
        etf_aligned        = etf_prices.reindex(constituent_prices.index).dropna()
        constituent_prices = constituent_prices.reindex(etf_aligned.index)

        spread = rolling_basket_spread(
            etf_aligned, constituent_prices, window=window,
            ridge_alpha=args.ridge_alpha,
            regime_filter=args.regime_filter,
        )

        # ADF on training-only portion for stationarity report
        calib_end    = (len(spread) - _PERIOD_BARS.get(test_period, 0)
                        if (test_period and not n_folds) else len(spread))
        calib_spread = spread.iloc[:calib_end].dropna()
        adf = adf_test(calib_spread)
        hl  = compute_half_life(calib_spread)
        hl_str = f"{hl:.1f}d" if hl != float("inf") else "inf"
        suppressed = spread.isna().sum() - window  # NaN beyond warm-up = regime-filtered bars
        regime_note = f"  regime-filtered: {suppressed}d" if args.regime_filter > 0 and suppressed > 0 else ""
        print(f"  ADF p={adf['p_value']:.4f}  HL={hl_str}  "
              f"({'stationary' if adf['is_stationary'] else 'NON-STATIONARY'}){regime_note}")

        signals, _ = generate_basket_signals(
            spread, window=window,
            z_entry=args.z_entry, z_exit=args.z_exit, z_stop=args.z_stop,
            vix_series=vix_series, vix_threshold=vix_filter,
        )

        basket_data.append((label, spread, signals, constituent_prices.shape[1], etf_aligned, stocks))

    if not basket_data:
        print("ERROR: No baskets ran successfully.")
        sys.exit(1)

    # ---- Phase 2a: Walk-forward (N non-overlapping OOS folds) ----
    if n_folds:
        ref_T      = len(basket_data[0][1])  # first leg's spread as reference
        train_bars = ref_T // period_years
        fold_bars  = max(1, (ref_T - train_bars) // n_folds)
        fold_label = (f"{round(fold_bars / 252)}y" if fold_bars >= 200
                      else f"{fold_bars}d")
        print(f"\nRunning walk-forward validation ({n_folds} folds x {fold_label})...")

        fold_combined_metrics = []
        all_stitched_pnls     = []

        for fold_k in range(n_folds):
            # fold_k=0 is the oldest window; fold_k=n_folds-1 is the most recent
            fold_leg_pnls  = []
            fold_n_trades  = 0
            fold_win_rates = []

            for label, spread, signals, n_stocks_leg, *_ in basket_data:
                T = len(spread)
                fold_start_idx = T - (n_folds - fold_k) * fold_bars
                fold_end_idx   = min(T - (n_folds - fold_k - 1) * fold_bars, T)

                if fold_start_idx < window + 10:
                    continue

                fold_start_date = spread.index[fold_start_idx]
                fold_end_date   = spread.index[fold_end_idx - 1]

                signals_fold = signals.loc[
                    (signals.index >= fold_start_date) & (signals.index <= fold_end_date)
                ]
                spread_fold = spread.loc[
                    (spread.index >= fold_start_date) & (spread.index <= fold_end_date)
                ]

                _, equity_fold, mf = run_basket_backtest(
                    signals_fold, spread_fold, capital=leg_capital,
                    cost_bps=args.cost_bps, n_stocks=n_stocks_leg,
                    max_hold_days=max_hold_days, vol_target=vol_target,
                )
                fold_n_trades += mf.get("n_trades", 0)
                wr = mf.get("win_rate")
                if wr is not None and not (isinstance(wr, float) and _math.isnan(wr)):
                    fold_win_rates.append(wr)

                if mf.get("n_trades", 0) > 0:
                    daily_pnl = equity_fold["equity"].diff().fillna(0)
                    fold_leg_pnls.append(daily_pnl.rename(label))

            if not fold_leg_pnls:
                print(f"  Fold {fold_k + 1}: insufficient data, skipping.")
                continue

            fold_pnl_df   = pd.concat(fold_leg_pnls, axis=1, sort=True).fillna(0)
            fold_comb_pnl = fold_pnl_df.sum(axis=1)
            fold_equity   = (total_capital + fold_comb_pnl.cumsum()).to_frame("equity")

            fm = _compute_metrics(fold_equity, total_capital)
            fm["n_trades"] = fold_n_trades
            fm["win_rate"] = (sum(fold_win_rates) / len(fold_win_rates)
                              if fold_win_rates else float("nan"))
            fm["start"] = fold_comb_pnl.index[0]
            fm["end"]   = fold_comb_pnl.index[-1]
            fm["fold"]  = fold_k + 1

            fold_combined_metrics.append(fm)
            all_stitched_pnls.append(fold_comb_pnl)

            print(f"  Fold {fold_k + 1} ({fm['start'].date()} to {fm['end'].date()}): "
                  f"{fm['total_return']:.1%} return  |  Sharpe {fm['sharpe']:.2f}  |  "
                  f"{fold_n_trades} trades")

        if not all_stitched_pnls:
            print("ERROR: No fold data available.")
            sys.exit(1)

        full_pnl        = pd.concat(all_stitched_pnls).sort_index()
        stitched_equity = (total_capital + full_pnl.cumsum()).to_frame("equity")
        overall         = _compute_metrics(stitched_equity, total_capital)
        overall["n_trades"] = sum(fm["n_trades"] for fm in fold_combined_metrics)
        all_wrs = [fm["win_rate"] for fm in fold_combined_metrics
                   if not (isinstance(fm["win_rate"], float) and _math.isnan(fm["win_rate"]))]
        overall["win_rate"] = sum(all_wrs) / len(all_wrs) if all_wrs else float("nan")
        overall["start"]    = stitched_equity.index[0]
        overall["end"]      = stitched_equity.index[-1]

        print(
            f"\nWalk-Forward ({n_folds} folds): "
            f"{overall['total_return']:.1%} return  |  "
            f"Sharpe {overall['sharpe']:.2f}  |  "
            f"Max DD {overall['max_drawdown']:.1%}  |  "
            f"{overall['n_trades']} trades total"
        )

        print("Opening windows...")
        _show(
            plot_walk_forward_results(stitched_equity, fold_combined_metrics, overall, params),
            f"Walk-Forward -- {' + '.join(lb for lb, *_ in basket_data)}",
        )
        return

    # ---- Phase 2b: Single OOS mode (existing behaviour) ----
    leg_equities = {}
    leg_metrics  = {}
    leg_extras   = {}   # label → {trades, etf_aligned, basket_prices, spread, signals, stocks}
    daily_pnls   = []

    for label, spread, signals, n_stocks_leg, etf_aligned, stocks in basket_data:
        T = len(spread)
        split_date = None
        if test_period:
            n_test = _PERIOD_BARS.get(test_period, 252)
            if n_test < T - window - 10:
                split_idx  = T - n_test
                split_date = spread.index[split_idx]

        if split_date is not None:
            signals_bt = signals.loc[signals.index >= split_date]
            spread_bt  = spread.loc[spread.index >= split_date]
        else:
            signals_bt, spread_bt = signals, spread

        trades, equity_curve, metrics = run_basket_backtest(
            signals_bt, spread_bt, capital=leg_capital,
            cost_bps=args.cost_bps, n_stocks=n_stocks_leg,
            max_hold_days=max_hold_days, vol_target=vol_target,
        )
        n_t = metrics.get("n_trades", 0)
        ret = metrics.get("total_return", 0.0)
        sh  = metrics.get("sharpe", 0.0)
        print(f"  {label}: {n_t} trades  |  {ret:.1%} return  |  Sharpe {sh:.2f}")

        leg_equities[label] = equity_curve
        leg_metrics[label]  = metrics
        leg_extras[label]   = {
            "trades":        trades,
            "etf_aligned":   etf_aligned,
            "basket_prices": etf_aligned * np.exp(-spread),
            "spread":        spread,
            "signals":       signals,
            "stocks":        stocks,
        }

        daily_pnl = equity_curve["equity"].diff().fillna(0)
        daily_pnls.append(daily_pnl.rename(label))

    if not leg_equities:
        print("ERROR: No baskets ran successfully.")
        sys.exit(1)

    # Combine equity curves
    pnl_df  = pd.concat(daily_pnls, axis=1, sort=True).fillna(0)
    combined_pnl           = pnl_df.sum(axis=1)
    combined_equity_series = total_capital + combined_pnl.cumsum()
    combined_equity_series.index.name = "date"
    combined_equity = combined_equity_series.to_frame("equity")

    combined_metrics = _compute_metrics(combined_equity, total_capital)
    combined_metrics["n_trades"] = sum(m.get("n_trades", 0) for m in leg_metrics.values())
    win_rates = [m.get("win_rate", float("nan")) for m in leg_metrics.values()
                 if not (isinstance(m.get("win_rate"), float) and
                         _math.isnan(m.get("win_rate", float("nan"))))]
    combined_metrics["win_rate"] = (sum(win_rates) / len(win_rates)
                                    if win_rates else float("nan"))

    period_label = f"({test_period} OOS)" if test_period else f"({period} full)"
    print(
        f"\nCombined portfolio {period_label}: "
        f"{combined_metrics['total_return']:.1%} return  |  "
        f"Sharpe {combined_metrics['sharpe']:.2f}  |  "
        f"Max DD {combined_metrics['max_drawdown']:.1%}"
    )

    # Align individual leg equities to combined index for clean plotting.
    # fillna(leg_capital) fills any leading NaN (before the leg's first trade)
    # so normalisation in plot_basket_legs always has a valid starting value.
    for label in list(leg_equities):
        eq = (leg_equities[label]["equity"]
              .reindex(combined_equity.index)
              .ffill()
              .fillna(leg_capital))
        leg_equities[label] = eq.to_frame("equity")

    print("Opening windows...")
    _show(
        plot_basket_combined(combined_equity, combined_metrics,
                             list(leg_equities.keys()), params),
        "Basket Portfolio -- Combined",
    )
    _show(
        plot_basket_legs(leg_equities, leg_metrics, params),
        "Basket Portfolio -- Individual ETFs",
    )

    if getattr(args, "monte_carlo", False):
        from src.backtest.monte_carlo import bootstrap_returns
        from src.strategies.basket.viz import plot_monte_carlo
        n_sims = getattr(args, "mc_sims", 10_000)
        print(f"Running Monte Carlo bootstrap ({n_sims:,} sims, daily-returns)...")
        mc = bootstrap_returns(combined_equity, capital=total_capital, n_sims=n_sims)
        _print_mc_summary(mc)
        _show(plot_monte_carlo(mc, combined_metrics, "Portfolio", params),
              "Basket Portfolio -- Monte Carlo")

    # Per-leg spread and trade P&L breakdown charts
    from src.strategies.basket.viz import plot_basket_spread, plot_basket_trade_pnl
    from src.strategies.pairs.signals import compute_zscore as _compute_zscore
    for lbl, extra in leg_extras.items():
        etf_al   = extra["etf_aligned"]
        basket_p = extra["basket_prices"]
        spread_l = extra["spread"]
        signals_l = extra["signals"]
        stocks_l  = extra["stocks"]
        trades_l  = extra["trades"]
        zscore_l  = _compute_zscore(spread_l, window=window)

        _show(
            plot_basket_spread(spread_l, zscore_l, signals_l, lbl, stocks_l, params,
                               etf_prices=etf_al, basket_prices=basket_p),
            f"Basket — {lbl} — Spread",
        )

        if not trades_l.empty:
            etf_at_entry = etf_al.reindex(trades_l["entry_date"]).values
            etf_at_exit  = etf_al.reindex(trades_l["exit_date"]).values
            bsk_at_entry = basket_p.reindex(trades_l["entry_date"]).values
            bsk_at_exit  = basket_p.reindex(trades_l["exit_date"]).values
            etf_log_ret  = np.log(etf_at_exit  / etf_at_entry)
            bsk_log_ret  = np.log(bsk_at_exit  / bsk_at_entry)
            direction    = trades_l["direction"].values
            notional     = trades_l["notional"].values
            etf_pct_arr  = direction *  etf_log_ret * notional / leg_capital
            bsk_pct_arr  = direction * -bsk_log_ret * notional / leg_capital
            _show(
                plot_basket_trade_pnl(trades_l, lbl, etf_pct_arr, bsk_pct_arr),
                f"Basket — {lbl} — Trade P&L",
            )


def _register_basket_multi(subparsers):
    parser = subparsers.add_parser(
        "basket-multi",
        help="Run multiple basket/ETF strategies as a combined portfolio",
    )
    parser.add_argument(
        "--basket", dest="baskets", required=True, action="append", metavar="ETF:S1,S2,...",
        help="ETF and its constituents. Repeat for each leg, e.g. "
             "--basket XLF:GS,MS,JPM --basket XLE:XOM,CVX,COP",
    )
    parser.add_argument("--period",   default="5y",  help="Data lookback (default: 5y)")
    parser.add_argument("--window",   default=60, type=int,
                        help="Rolling OLS and z-score window in days (default: 60)")
    parser.add_argument("--z-entry",  default=1.5, type=float,
                        help="Entry threshold (default: 1.5)")
    parser.add_argument("--z-exit",   default=0.5, type=float,
                        help="Exit threshold (default: 0.5)")
    parser.add_argument("--z-stop",   default=3.0, type=float,
                        help="Stop-loss threshold (default: 3.0)")
    parser.add_argument("--cost-bps",  default=5.0, type=float, metavar="BPS",
                        help="Round-trip transaction cost in basis points per trade (default: 5)")
    parser.add_argument("--test-period", default=None, metavar="PERIOD",
                        choices=["3mo", "6mo", "1y", "2y"],
                        help="Hold out the most recent PERIOD as out-of-sample test window.")
    parser.add_argument("--walk-forward", default=None, type=int, nargs="?", const=-1,
                        metavar="N", dest="walk_forward",
                        help="Walk-forward validation. Without N: auto-selects folds from "
                             "period (5y→4, 3y→2, 10y→9). With N: splits OOS evenly into N "
                             "folds (e.g. --period 5y --walk-forward 2 = two 2-year folds). "
                             "Overrides --test-period.")
    parser.add_argument("--ridge-alpha", default=0.0, type=float, metavar="A",
                        dest="ridge_alpha",
                        help="Ridge (L2) regularisation for OLS basket fit (default: 0 = off). "
                             "Reduces overfitting when n_stocks/window is high. Try 0.05–0.20.")
    parser.add_argument("--regime-filter", default=0.0, type=float, metavar="T",
                        dest="regime_filter",
                        help="Suppress spread when normalised OLS coefficient shift exceeds T "
                             "(default: 0 = off). Detects structural breaks. Try 0.20–0.50.")
    parser.add_argument("--static", action="store_true", dest="static_constituents",
                        help="Use today's fixed basket composition instead of EDGAR N-PORT history "
                             "(survivorship bias warning). Supply stocks via --basket ETF:S1,S2,...")
    parser.add_argument("--dynamic-constituents", action="store_true", dest="dynamic_constituents",
                        help="(Deprecated — dynamic is now the default. Has no effect.)")
    parser.add_argument("--edgar-constituents", action="store_true", dest="edgar_constituents",
                        help="(Deprecated alias for --dynamic-constituents.)")
    parser.add_argument("--top-n", default=5, type=int, dest="top_n", metavar="N",
                        help="Number of top ETF holdings to track from EDGAR N-PORT (default: 5).")
    parser.add_argument("--max-hold-days", default=0, type=int, metavar="N", dest="max_hold_days",
                        help="Force-close positions held longer than N calendar days (0 = off, e.g. 30).")
    parser.add_argument("--vix-filter", default=0.0, type=float, metavar="LEVEL", dest="vix_filter",
                        help="Suppress new entries when VIX > LEVEL (0 = off, e.g. 25).")
    parser.add_argument("--vol-target", default=0.0, type=float, metavar="F", dest="vol_target",
                        help="Annualised spread vol target as fraction of capital (0 = off, e.g. 0.10).")
    parser.add_argument("--monte-carlo", action="store_true", dest="monte_carlo",
                        help="Run Monte Carlo bootstrap on combined portfolio after backtest.")
    parser.add_argument("--mc-sims", default=10_000, type=int, dest="mc_sims",
                        help="Number of Monte Carlo simulations (default: 5000).")
    parser.add_argument("--factor-analysis", action="store_true", dest="factor_analysis",
                        help="Run Fama-French 5-factor regression on combined portfolio returns "
                             "and save figure. Skips standard portfolio charts.")
    parser.add_argument("--save-images", default=None, metavar="DIR", dest="save_images",
                        help="Export all figures as PNG files to DIR (requires kaleido).")
    parser.add_argument("--save-figs", default=None, metavar="DIR", dest="save_figs",
                        help="Save all figures as Plotly JSON to DIR (used by Streamlit app).")
    parser.set_defaults(func=_run_basket_multi)


def _register_basket(subparsers):
    parser = subparsers.add_parser("basket", help="Basket / ETF arbitrage")
    parser.add_argument("--etf",     required=True, metavar="TICKER",
                        help="ETF ticker to trade against the basket, e.g. XLF")
    parser.add_argument("--stocks",  required=False, nargs="+", metavar="TICKER", default=None,
                        help="Constituent tickers, e.g. GS MS JPM BAC C. "
                             "Used in --static mode or as pre-EDGAR fallback.")
    parser.add_argument("--static", action="store_true", dest="static_constituents",
                        help="Use today's fixed composition instead of EDGAR N-PORT history "
                             "(survivorship bias warning). Requires --stocks.")
    parser.add_argument("--dynamic-constituents", action="store_true", dest="dynamic_constituents",
                        help="(Deprecated — dynamic is now the default. Has no effect.)")
    parser.add_argument("--top-n", default=5, type=int, dest="top_n", metavar="N",
                        help="Number of top ETF holdings to track from EDGAR N-PORT (default: 5).")
    parser.add_argument("--period",  default="2y",  help="Data lookback (default: 2y)")
    parser.add_argument("--window",  default=60, type=int,
                        help="Rolling OLS and z-score window in days (default: 60)")
    parser.add_argument("--z-entry", default=2.0, type=float,
                        help="Entry threshold (default: 2.0)")
    parser.add_argument("--z-exit",  default=0.5, type=float,
                        help="Exit threshold (default: 0.5)")
    parser.add_argument("--z-stop",  default=3.0, type=float,
                        help="Stop-loss threshold (default: 3.0)")
    parser.add_argument("--test-period", default=None, metavar="PERIOD",
                        choices=["3mo", "6mo", "1y", "2y"],
                        help="Hold out the most recent PERIOD as out-of-sample test window.")
    parser.add_argument("--data-provider", default="yfinance", metavar="PROVIDER",
                        choices=["yfinance", "alpaca"], dest="data_provider",
                        help="Price data source: yfinance (default) or alpaca.")
    parser.add_argument("--cost-bps", default=2.0, type=float, metavar="BPS",
                        help="Round-trip transaction cost in basis points (default: 2.0).")
    parser.add_argument("--walk-forward", default=None, type=int, nargs="?", const=-1,
                        dest="walk_forward",
                        help="Run walk-forward validation. Optionally pass N folds; omit N to auto-derive from --period.")
    parser.add_argument("--max-hold-days", default=0, type=int, metavar="N", dest="max_hold_days",
                        help="Force-close positions held longer than N calendar days (0 = off, e.g. 30).")
    parser.add_argument("--vix-filter", default=0.0, type=float, metavar="LEVEL", dest="vix_filter",
                        help="Suppress new entries when VIX > LEVEL (0 = off, e.g. 25).")
    parser.add_argument("--vol-target", default=0.0, type=float, metavar="F", dest="vol_target",
                        help="Annualised spread vol target as fraction of capital (0 = off, e.g. 0.10).")
    parser.add_argument("--monte-carlo", action="store_true", dest="monte_carlo",
                        help="Run Monte Carlo bootstrap on trade P&L after backtest.")
    parser.add_argument("--mc-sims", default=10_000, type=int, dest="mc_sims",
                        help="Number of Monte Carlo simulations (default: 5000).")
    parser.add_argument("--save-images", default=None, metavar="DIR", dest="save_images",
                        help="Export all figures as PNG files to DIR (requires kaleido).")
    parser.add_argument("--save-figs", default=None, metavar="DIR", dest="save_figs",
                        help="Save all figures as Plotly JSON to DIR (used by Streamlit app).")
    parser.set_defaults(func=_run_basket)


# ---------------------------------------------------------------------------
# basket-history: fetch EDGAR N-PORT constituent history for one or more ETFs
# ---------------------------------------------------------------------------
def _run_basket_history(args):
    from src.data.edgar import build_constituent_history, get_constituents_at, summarize_changes

    etfs        = [e.strip().upper() for e in args.etfs]
    period      = args.period
    top_n       = args.top_n
    show_changes = not args.no_changes

    # Map period string to approximate start date
    period_years = {"1y": 1, "2y": 2, "3y": 3, "5y": 5}.get(period, 2)
    end_date   = pd.Timestamp.today().normalize()
    start_date = end_date - pd.DateOffset(years=period_years)

    for etf in etfs:
        print(f"\n{'='*60}")
        print(f"EDGAR N-PORT history for {etf} ({period})")
        print(f"{'='*60}")

        try:
            history = build_constituent_history(
                etf,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                top_n=top_n,
            )
        except ValueError as e:
            print(f"  ERROR: {e}")
            continue

        if history.empty:
            print(f"  No filings found.")
            continue

        # Latest composition
        latest = history.iloc[-1]
        print(f"\nLatest filing ({latest['filing_date'].date()}) — {len(latest['constituents'])} positions:")
        for ticker, weight in zip(latest["constituents"][:20], latest["weights"][:20]):
            print(f"  {ticker:<8}  {weight:5.2f}%")
        if len(latest["constituents"]) > 20:
            print(f"  ... ({len(latest['constituents']) - 20} more)")

        # Earliest filing for comparison
        earliest = history.iloc[0]
        today_set   = set(latest["constituents"])
        earliest_set = set(earliest["constituents"])
        added_since   = sorted(today_set - earliest_set)
        removed_since = sorted(earliest_set - today_set)

        print(f"\nComposition change since earliest filing ({earliest['filing_date'].date()}):")
        if added_since:
            print(f"  Added   ({len(added_since)}): {', '.join(added_since)}")
        if removed_since:
            print(f"  Removed ({len(removed_since)}): {', '.join(removed_since)}")
        if not added_since and not removed_since:
            print("  No changes — composition identical to earliest filing.")

        # Quarter-by-quarter change log
        if show_changes:
            changes = summarize_changes(history)
            any_change = changes[changes["added"].apply(len) + changes["removed"].apply(len) > 0]
            if any_change.empty:
                print(f"\nQuarterly changes: none over the period.")
            else:
                print(f"\nQuarterly changes ({len(any_change)} events):")
                for _, row in any_change.iterrows():
                    parts = []
                    if row["added"]:
                        parts.append(f"+{','.join(row['added'])}")
                    if row["removed"]:
                        parts.append(f"-{','.join(row['removed'])}")
                    print(f"  {row['filing_date'].date()}  {'  '.join(parts)}")

        # Survivorship-bias impact estimate
        if removed_since:
            print(f"\nSurvivorship-bias note: {len(removed_since)} stock(s) removed over the period.")
            print("  Running a backtest with today's constituents excludes these names,")
            print("  which may have been removed due to poor performance (downward bias removal).")
            print(f"  Consider using --stocks with the earliest-period constituents:")
            earliest_top = earliest["constituents"][:top_n] if top_n else earliest["constituents"]
            print(f"  {' '.join(earliest_top)}")


def _register_basket_history(subparsers):
    parser = subparsers.add_parser(
        "basket-history",
        help="Fetch EDGAR N-PORT constituent history for ETFs (survivorship bias check)",
    )
    parser.add_argument(
        "etfs", nargs="+", metavar="ETF",
        help="ETF ticker(s) to look up, e.g. XLF XLE XLK",
    )
    parser.add_argument(
        "--period", default="5y", choices=["1y", "2y", "3y", "5y"],
        help="How far back to fetch filings (default: 5y)",
    )
    parser.add_argument(
        "--top-n", default=None, type=int, metavar="N",
        help="Show only the top-N holdings by weight (default: all)",
    )
    parser.add_argument(
        "--no-changes", action="store_true",
        help="Skip the quarter-by-quarter change log (faster output)",
    )
    parser.set_defaults(func=_run_basket_history)


# ---------------------------------------------------------------------------
# cta: multi-horizon EWMAC trend-following across a diversified ETF universe
# ---------------------------------------------------------------------------
def _run_cta(args):
    import math as _math
    from src.data.fetcher import fetch_prices_bulk
    from src.analytics.cta import vol_targeted_weights
    from src.strategies.cta.signals import CTA_UNIVERSE, generate_cta_positions
    from src.strategies.cta.viz import (
        plot_cta_equity, plot_cta_signals, plot_cta_contributions,
        plot_cta_sweep_heatmap, plot_cta_walk_forward,
    )
    from src.backtest.portfolio_engine import run_portfolio_backtest, _compute_metrics

    universe_name = args.universe.lower()
    if universe_name not in CTA_UNIVERSE:
        print(f"ERROR: Unknown universe '{args.universe}'. Available: {', '.join(CTA_UNIVERSE)}")
        sys.exit(1)

    tickers = CTA_UNIVERSE[universe_name]
    period  = args.period

    provider = getattr(args, "data_provider", "yfinance")
    print(f"Fetching {len(tickers)} tickers ({period}, provider={provider})...")
    prices_dict = fetch_prices_bulk(tickers, period=period, provider=provider)
    if len(prices_dict) < 2:
        print("ERROR: Need at least 2 tickers with data.")
        sys.exit(1)

    prices_df = pd.DataFrame(prices_dict)

    min_obs = int(0.80 * len(prices_df))
    prices_df = prices_df.dropna(thresh=min_obs, axis=1)
    prices_df = prices_df.dropna()

    n_instruments = prices_df.shape[1]
    dropped = len(prices_dict) - n_instruments
    if dropped:
        print(f"  Dropped {dropped} ticker(s) with insufficient history.")
    print(f"Aligned {n_instruments} instruments over {len(prices_df)} bars.")

    signal_mode   = getattr(args, "signal_mode", "binary")
    corr_adjust   = getattr(args, "corr_adjust", False)
    n_folds       = getattr(args, "walk_forward", None)
    do_sweep      = getattr(args, "sweep", False)
    use_regime    = getattr(args, "regime_filter", False)

    spy_prices = None
    if use_regime:
        from src.data.fetcher import fetch_price as _fetch_price
        try:
            spy_prices = _fetch_price("SPY", period=period)
            spy_prices = spy_prices.reindex(prices_df.index).ffill()
            print("Regime filter: SPY 200-day MA (equity longs suppressed in risk-off)...")
        except Exception:
            print("WARNING: Could not fetch SPY for regime filter — filter disabled.")

    # ── Sweep mode: grid search over parameters ───────────────────────────────
    if do_sweep:
        from src.strategies.cta.sweep import sweep_cta_params
        fold_bars = 252
        n_sweep_folds = 5
        T = len(prices_df)
        fold_starts, fold_ends = [], []
        for k in range(n_sweep_folds):
            start_idx = T - (n_sweep_folds - k) * fold_bars
            end_idx   = min(T - (n_sweep_folds - k - 1) * fold_bars, T) - 1
            if start_idx < 300:
                continue
            fold_starts.append(prices_df.index[start_idx])
            fold_ends.append(prices_df.index[end_idx])

        if not fold_starts:
            print("ERROR: Not enough data for sweep folds. Use --period 10y or longer.")
            sys.exit(1)

        print(f"Running parameter sweep ({len(fold_starts)} folds)...")
        sweep_results = sweep_cta_params(
            prices_df, fold_starts, fold_ends,
            tau=args.vol_target, cost_bps=args.cost_bps, capital=args.capital,
        )

        if sweep_results.empty:
            print("ERROR: Sweep returned no results.")
            sys.exit(1)

        print("\nSweep results (Sharpe mean across folds):")
        for mode in sweep_results.index.get_level_values("signal_mode").unique():
            mode_df = sweep_results.xs(mode, level="signal_mode")["sharpe_mean"].unstack("vol_span")
            print(f"\n  [{mode}]")
            print(mode_df.to_string(float_format=lambda x: f"{x:+.2f}"))

        print("\nOpening sweep heatmap...")
        _show(plot_cta_sweep_heatmap(sweep_results), "CTA -- Parameter Sweep")
        return

    pairs = ((8, 32), (16, 64), (32, 128), (64, 256))
    weight_cap = args.weight_cap if args.weight_cap > 0 else None

    regime_label = ", regime_filter=SPY_200MA" if use_regime and spy_prices is not None else ""
    print(f"Computing EWMAC signals (mode={signal_mode}, threshold={args.threshold}{regime_label})...")
    positions_df, signals_df = generate_cta_positions(
        prices_df, pairs=pairs, threshold=args.threshold, signal_mode=signal_mode,
        spy_prices=spy_prices,
    )

    corr_label = ", corr_adjust=True" if corr_adjust else ""
    print(f"Applying vol targeting (tau={args.vol_target:.0%}, vol_span={args.vol_span}, cap={weight_cap or 'none'}{corr_label})...")
    weights_df = vol_targeted_weights(
        positions_df, prices_df,
        tau=args.vol_target,
        vol_span=args.vol_span,
        weight_cap=weight_cap,
        corr_adjust=corr_adjust,
    )

    # ── Walk-forward mode ────────────────────────────────────────────────────
    if n_folds:
        print(f"\nRunning walk-forward validation ({n_folds} folds × 1y)...")
        fold_bars = 252
        T = len(prices_df)

        fold_combined_metrics = []
        all_stitched_pnls     = []

        for fold_k in range(n_folds):
            start_idx = T - (n_folds - fold_k) * fold_bars
            end_idx   = min(T - (n_folds - fold_k - 1) * fold_bars, T)

            if start_idx < 300:
                print(f"  Fold {fold_k + 1}: insufficient warm-up data, skipping.")
                continue

            fold_start = prices_df.index[start_idx]
            fold_end   = prices_df.index[end_idx - 1]

            mask         = (prices_df.index >= fold_start) & (prices_df.index <= fold_end)
            prices_fold  = prices_df.loc[mask]
            pos_fold     = positions_df.loc[mask]
            weights_fold = weights_df.loc[mask]

            equity_fold, fm = run_portfolio_backtest(
                pos_fold, prices_fold, capital=args.capital,
                cost_bps=args.cost_bps, weights_df=weights_fold,
            )

            fm["start"] = fold_start
            fm["end"]   = fold_end
            fm["fold"]  = fold_k + 1

            fold_combined_metrics.append(fm)
            daily_pnl = equity_fold["equity"].diff().fillna(0)
            all_stitched_pnls.append(daily_pnl)

            print(f"  Fold {fold_k + 1} ({fold_start.date()} to {fold_end.date()}): "
                  f"{fm['total_return']:.1%} return  |  Sharpe {fm['sharpe']:.2f}")

        if not all_stitched_pnls:
            print("ERROR: No fold data. Use a longer --period.")
            sys.exit(1)

        full_pnl        = pd.concat(all_stitched_pnls).sort_index()
        stitched_equity = (args.capital + full_pnl.cumsum()).to_frame("equity")
        overall         = _compute_metrics(stitched_equity, args.capital)
        overall["start"] = stitched_equity.index[0]
        overall["end"]   = stitched_equity.index[-1]

        print(
            f"\nWalk-Forward ({n_folds} folds): "
            f"{overall['total_return']:.1%} return  |  "
            f"Sharpe {overall['sharpe']:.2f}  |  "
            f"Max DD {overall['max_drawdown']:.1%}"
        )

        wf_params = {
            "period":       period,
            "universe":     universe_name.capitalize(),
            "signal_mode":  signal_mode,
            "vol_target":   f"{args.vol_target:.0%}",
            "threshold":    args.threshold,
            "cost_bps":     args.cost_bps,
        }
        print("Opening windows...")
        _show(
            plot_cta_walk_forward(stitched_equity, fold_combined_metrics, overall, wf_params),
            f"CTA -- {universe_name.capitalize()} -- Walk-Forward",
        )
        return

    # ── Single train/test split (existing behaviour) ─────────────────────────
    split_date  = None
    test_period = args.test_period
    if test_period:
        n_test = _PERIOD_BARS.get(test_period, 252)
        if n_test >= len(prices_df) - 300:
            print(f"WARNING: --test-period '{test_period}' leaves too little data. Ignoring.")
            test_period = None
        else:
            split_idx  = len(prices_df) - n_test
            split_date = prices_df.index[split_idx]
            print(f"Train/test split — up to {split_date.date()}  |  test: {test_period} forward")

    if split_date is not None:
        prices_bt    = prices_df.loc[prices_df.index >= split_date]
        positions_bt = positions_df.loc[positions_df.index >= split_date]
        signals_bt   = signals_df.loc[signals_df.index >= split_date]
        weights_bt   = weights_df.loc[weights_df.index >= split_date]
        print(f"Backtesting on test period ({split_date.date()} to {prices_bt.index[-1].date()})")
    else:
        prices_bt, positions_bt, signals_bt = prices_df, positions_df, signals_df
        weights_bt = weights_df

    avg_gross = weights_bt.abs().sum(axis=1).mean()
    print(f"Average gross leverage: {avg_gross:.2f}x")

    cost_model = getattr(args, "cost_model", "fixed")
    cost_df_bt = None
    if cost_model == "volume-adjusted":
        from src.data.fetcher import fetch_ohlcv_bulk
        from src.analytics.costs import estimate_cost_bps
        print("Fetching OHLCV for volume-adjusted cost model...")
        ohlcv = fetch_ohlcv_bulk(list(prices_bt.columns), period=period, provider=provider)
        cost_series = {
            t: estimate_cost_bps(
                ohlcv[t]["close"], ohlcv[t]["volume"],
                order_notional=args.capital / max(1, n_instruments),
            )
            for t in prices_bt.columns if t in ohlcv
        }
        if cost_series:
            cost_df_bt = pd.DataFrame(cost_series).reindex(prices_bt.index)
            avg_cost = cost_df_bt.mean().mean()
            print(f"  Volume-adjusted cost: avg {avg_cost:.1f}bps (vs flat {args.cost_bps}bps)")

    print(f"Running portfolio backtest ({n_instruments} instruments, cost={args.cost_bps}bps)...")
    equity_curve, bt_metrics = run_portfolio_backtest(
        positions_bt, prices_bt, capital=args.capital, cost_bps=args.cost_bps,
        weights_df=weights_bt, cost_df=cost_df_bt,
    )

    period_label = f"({test_period} test)" if test_period else f"({period} full)"
    print(
        f"CTA Trend Following {period_label}: "
        f"{bt_metrics['total_return']:.1%} return  |  "
        f"Sharpe {bt_metrics['sharpe']:.2f}  |  "
        f"Max DD {bt_metrics['max_drawdown']:.1%}"
    )

    params = {
        "period":        period,
        "n_instruments": n_instruments,
        "vol_target":    f"{args.vol_target:.0%}",
        "threshold":     args.threshold,
        "cost_bps":      args.cost_bps,
        "test_period":   test_period,
    }
    universe_label = universe_name.capitalize()

    print("Opening windows...")
    _show(plot_cta_equity(equity_curve, bt_metrics, universe_label, params),
          f"CTA -- {universe_label} -- Equity")
    _show(plot_cta_signals(signals_bt, positions_bt, universe_label),
          f"CTA -- {universe_label} -- Signals")
    _show(plot_cta_contributions(equity_curve, positions_bt, prices_bt,
                                  universe_label, args.capital, weights_df=weights_bt),
          f"CTA -- {universe_label} -- Contributions")


def _register_cta(subparsers):
    from src.strategies.cta.signals import CTA_UNIVERSE
    parser = subparsers.add_parser("cta", help="CTA trend-following (multi-horizon EWMAC)")
    parser.add_argument(
        "--universe", default="default", metavar="NAME",
        help=f"Instrument universe preset. Options: {', '.join(CTA_UNIVERSE)} (default: default)",
    )
    parser.add_argument("--period",    default="5y",
                        help="Data lookback (default: 5y)")
    parser.add_argument("--test-period", default="1y", metavar="PERIOD",
                        choices=["3mo", "6mo", "1y", "2y"],
                        help="Hold out the most recent PERIOD as out-of-sample test window (default: 1y)")
    parser.add_argument("--walk-forward", default=None, type=int, metavar="N",
                        dest="walk_forward",
                        help="Run N non-overlapping 1-year OOS folds (overrides --test-period)")
    parser.add_argument("--sweep", action="store_true",
                        help="Run parameter grid search (threshold × vol_span × signal_mode) and show heatmap")
    parser.add_argument("--signal-mode", default="binary", metavar="MODE",
                        choices=["binary", "continuous"], dest="signal_mode",
                        help="Position sizing mode: binary={-1,0,+1} or continuous=scaled ±1 (default: binary)")
    parser.add_argument("--corr-adjust", action="store_true", dest="corr_adjust",
                        help="Scale vol-targeted weights by correlation-adjusted portfolio vol to hit tau")
    parser.add_argument("--regime-filter", action="store_true", dest="regime_filter",
                        help="Suppress long equity positions when SPY is below its 200-day MA (risk-off filter)")
    parser.add_argument("--threshold", default=0.0, type=float, metavar="T",
                        help="Signal flat-band: |EWMAC| must exceed T to enter a position (default: 0)")
    parser.add_argument("--vol-target", default=0.20, type=float, metavar="TAU",
                        dest="vol_target",
                        help="Annualised portfolio vol target for position sizing (default: 0.20 = 20%%)")
    parser.add_argument("--vol-span", default=25, type=int, metavar="N",
                        dest="vol_span",
                        help="EWM span (days) for per-instrument vol estimation in position sizing (default: 25)")
    parser.add_argument("--weight-cap", default=0.0, type=float, metavar="W",
                        dest="weight_cap",
                        help="Per-instrument weight cap as fraction of capital (default: 0 = no cap)")
    parser.add_argument("--cost-bps",  default=5.0, type=float, metavar="BPS",
                        help="Transaction cost per unit of portfolio turnover in bps (default: 5)")
    parser.add_argument("--capital",   default=20_000.0, type=float, metavar="DOLLARS",
                        help="Starting capital (default: 20000)")
    parser.add_argument("--data-provider", default="yfinance", metavar="PROVIDER",
                        choices=["yfinance", "alpaca"], dest="data_provider",
                        help="Price data source: yfinance (default) or alpaca "
                             "(requires ALPACA_API_KEY / ALPACA_SECRET_KEY env vars)")
    parser.add_argument("--cost-model", default="fixed", metavar="MODEL",
                        choices=["fixed", "volume-adjusted"], dest="cost_model",
                        help="Transaction cost model: fixed (flat cost_bps, default) or "
                             "volume-adjusted (Kyle's lambda estimate using ADV)")
    parser.set_defaults(func=_run_cta)


# ---------------------------------------------------------------------------
# portfolio: equal-risk-weighted combination of all four strategies
# ---------------------------------------------------------------------------

_PORTFOLIO_BASKETS = [
    ("XLF", ["GS", "MS", "JPM", "BAC", "C"]),
    ("XLE", ["XOM", "CVX", "COP"]),
    ("XLK", ["MSFT", "AAPL", "NVDA"]),
    ("XLV", ["JNJ", "UNH", "ABT"]),
]


def _run_portfolio(args):
    import numpy as np
    from src.data.fetcher import fetch_prices_bulk, fetch_price
    from src.analytics.cta import vol_targeted_weights
    from src.strategies.cta.signals import CTA_UNIVERSE, generate_cta_positions
    from src.analytics.pca import rolling_pca_residuals
    from src.strategies.pca.signals import generate_pca_signals
    from src.analytics.basket import rolling_basket_spread
    from src.strategies.basket.signals import generate_basket_signals
    from src.strategies.basket.backtest import run_basket_backtest
    from src.backtest.portfolio_engine import run_portfolio_backtest, _compute_metrics
    from src.viz.portfolio import plot_portfolio_combined

    period     = args.period
    cost_bps   = args.cost_bps
    capital    = args.capital
    exclude    = set(getattr(args, "exclude", None) or [])
    leg_cap    = capital / max(1, 4 - len(exclude))

    per_strategy_equity  = {}
    per_strategy_metrics = {}

    # ── CTA ──────────────────────────────────────────────────────────────────
    if "cta" not in exclude:
        print("Running CTA strategy...")
        try:
            tickers = CTA_UNIVERSE["default"]
            pd_dict = fetch_prices_bulk(tickers, period=period)
            px = pd.DataFrame(pd_dict)
            px = px.dropna(thresh=int(0.80 * len(px)), axis=1).dropna()
            pos, _ = generate_cta_positions(px, threshold=0.0, signal_mode="binary")
            wt  = vol_targeted_weights(pos, px, tau=0.20)
            eq, m = run_portfolio_backtest(pos, px, capital=leg_cap, cost_bps=cost_bps, weights_df=wt)
            per_strategy_equity["CTA"]  = eq
            per_strategy_metrics["CTA"] = m
            print(f"  CTA: {m['total_return']:.1%} return  Sharpe {m['sharpe']:.2f}")
        except Exception as e:
            print(f"  CTA failed: {e}")

    # ── PCA ──────────────────────────────────────────────────────────────────
    if "pca" not in exclude:
        print("Running PCA strategy...")
        try:
            tickers = SCAN_UNIVERSES.get("financials", SCAN_UNIVERSES[next(iter(SCAN_UNIVERSES))])
            pd_dict = fetch_prices_bulk(tickers, period=period)
            px = pd.DataFrame(pd_dict).dropna()
            ret = px.pct_change().dropna()
            resid = rolling_pca_residuals(ret, window=60, n_components=3)
            pos, _ = generate_pca_signals(resid, window=60, z_entry=2.0, z_exit=0.5, z_stop=3.5)
            eq, m = run_portfolio_backtest(pos, px, capital=leg_cap, cost_bps=cost_bps)
            per_strategy_equity["PCA"]  = eq
            per_strategy_metrics["PCA"] = m
            print(f"  PCA: {m['total_return']:.1%} return  Sharpe {m['sharpe']:.2f}")
        except Exception as e:
            print(f"  PCA failed: {e}")

    # ── Basket ────────────────────────────────────────────────────────────────
    if "basket" not in exclude:
        print("Running Basket strategy...")
        try:
            basket_pnls = []
            basket_leg_cap = leg_cap / len(_PORTFOLIO_BASKETS)
            for etf, stocks in _PORTFOLIO_BASKETS:
                etf_px = fetch_price(etf, period=period)
                stocks_dict = {}
                for s in stocks:
                    try:
                        stocks_dict[s] = fetch_price(s, period=period)
                    except Exception:
                        pass
                if len(stocks_dict) < 2:
                    continue
                const_df   = pd.DataFrame(stocks_dict).dropna()
                etf_aligned = etf_px.reindex(const_df.index).dropna()
                const_df    = const_df.reindex(etf_aligned.index)
                spread = rolling_basket_spread(etf_aligned, const_df, window=60)
                sigs, _ = generate_basket_signals(spread, window=60, z_entry=1.5)
                _, eq_leg, _ = run_basket_backtest(
                    sigs, spread, capital=basket_leg_cap, cost_bps=cost_bps,
                    n_stocks=const_df.shape[1],
                )
                pnl = eq_leg["equity"].diff().fillna(0)
                basket_pnls.append(pnl.rename(etf))
            if basket_pnls:
                comb_pnl = pd.concat(basket_pnls, axis=1, sort=True).fillna(0).sum(axis=1)
                eq = (leg_cap + comb_pnl.cumsum()).to_frame("equity")
                m  = _compute_metrics(eq, leg_cap)
                per_strategy_equity["Basket"]  = eq
                per_strategy_metrics["Basket"] = m
                print(f"  Basket: {m['total_return']:.1%} return  Sharpe {m['sharpe']:.2f}")
        except Exception as e:
            print(f"  Basket failed: {e}")

    if not per_strategy_equity:
        print("ERROR: No strategies ran successfully.")
        sys.exit(1)

    # ── Combine with equal-risk weighting ─────────────────────────────────────
    print("Combining strategies with equal-risk weighting...")
    pnl_df = pd.DataFrame(
        {name: eq["equity"].diff().fillna(0) for name, eq in per_strategy_equity.items()}
    ).sort_index().ffill().fillna(0)

    # Rolling 63-day vol per strategy
    rolling_vol = pnl_df.rolling(63, min_periods=21).std() * np.sqrt(252)
    inv_vol  = 1.0 / rolling_vol.replace(0, np.nan)
    raw_wt   = inv_vol.div(inv_vol.sum(axis=1), axis=0).fillna(0)

    # Monthly rebalance
    monthly_wt = raw_wt.resample("MS").first().reindex(pnl_df.index, method="ffill").fillna(0)
    monthly_wt = monthly_wt.div(monthly_wt.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)

    combined_pnl    = (pnl_df * monthly_wt).sum(axis=1)
    combined_equity = (capital + combined_pnl.cumsum()).to_frame("equity")
    combined_metrics = _compute_metrics(combined_equity, capital)

    print(
        f"\nPortfolio ({', '.join(per_strategy_equity)}): "
        f"{combined_metrics['total_return']:.1%} return  |  "
        f"Sharpe {combined_metrics['sharpe']:.2f}  |  "
        f"Max DD {combined_metrics['max_drawdown']:.1%}"
    )

    params = {"period": period, "cost_bps": cost_bps}
    print("Opening window...")
    _show(
        plot_portfolio_combined(
            combined_equity, per_strategy_equity, per_strategy_metrics,
            combined_metrics, monthly_wt, params,
        ),
        "Multi-Strategy Portfolio",
    )


def _register_portfolio(subparsers):
    parser = subparsers.add_parser(
        "portfolio",
        help="Equal-risk-weighted combination of all strategies (CTA + PCA + Basket)",
    )
    parser.add_argument("--period",   default="5y",  help="Data lookback (default: 5y)")
    parser.add_argument("--cost-bps", default=5.0, type=float, metavar="BPS",
                        help="Transaction cost in bps (default: 5)")
    parser.add_argument("--capital",  default=100_000.0, type=float, metavar="DOLLARS",
                        help="Starting capital split across strategies (default: 100000)")
    parser.add_argument("--exclude",  nargs="*", default=None,
                        choices=["cta", "pca", "basket"],
                        help="Strategies to exclude (default: include all)")
    parser.set_defaults(func=_run_portfolio)


def _run_trade_basket(args, acct, capital, execute=False):
    """Basket/ETF arbitrage live trading logic."""
    import os as _os
    from src.data.fetcher import fetch_prices_bulk
    from src.analytics.basket import fit_basket, rolling_basket_spread
    from src.strategies.pairs.signals import compute_zscore
    from src.trading.alpaca_trader import place_notional_order, place_qty_order, close_position
    from alpaca.trading.enums import OrderSide

    etf           = args.etf.upper()
    top_n         = getattr(args, "top_n", 5)
    static_mode   = getattr(args, "static_constituents", False)

    if static_mode:
        stocks = [s.strip().upper() for s in (args.stocks or [])]
        if not stocks:
            print(f"ERROR: --static requires --stocks.")
            return
    else:
        from src.data.edgar import build_constituent_history, get_constituents_at
        today = pd.Timestamp.today().normalize()
        lookback = (today - pd.DateOffset(months=4)).strftime("%Y-%m-%d")
        history = build_constituent_history(etf, lookback, today.strftime("%Y-%m-%d"), top_n=top_n)
        stocks = get_constituents_at(history, today)
        if not stocks:
            print(f"ERROR: EDGAR returned no constituents for {etf}. Pass --static --stocks to override.")
            return
        print(f"EDGAR top-{top_n} for {etf} (today): {', '.join(stocks)}")

    # Alpaca uses dot notation (BRK.B) while EDGAR uses slash notation (BRK/B)
    stocks = [s.replace("/", ".") for s in stocks]

    window        = getattr(args, "window",        60)
    z_entry       = getattr(args, "z_entry",       1.5)
    z_exit        = getattr(args, "z_exit",        0.25)
    z_stop        = getattr(args, "z_stop",        2.5)
    vix_filter    = getattr(args, "vix_filter",    0.0)
    max_hold_days = getattr(args, "max_hold_days", 0)
    vol_target    = getattr(args, "vol_target",    0.0)

    has_keys = bool(_os.environ.get("ALPACA_API_KEY") and _os.environ.get("ALPACA_SECRET_KEY"))
    provider = "alpaca" if has_keys else "yfinance"
    print(f"Fetching {etf} + {len(stocks)} stocks (1y, provider={provider})...")
    prices = fetch_prices_bulk([etf] + stocks, period="1y", provider=provider)

    if etf not in prices:
        print(f"ERROR: Could not fetch {etf}.")
        return
    missing = [s for s in stocks if s not in prices]
    if missing:
        print(f"  WARNING: Could not fetch {missing}, skipping.")
    stocks = [s for s in stocks if s in prices]
    if len(stocks) < 2:
        print("ERROR: Need at least 2 constituent tickers.")
        return

    constituent_df = pd.DataFrame({s: prices[s] for s in stocks}).dropna()
    etf_aligned    = prices[etf].reindex(constituent_df.index).dropna()
    constituent_df = constituent_df.reindex(etf_aligned.index)

    spread = rolling_basket_spread(etf_aligned, constituent_df, window=window)
    zscore = compute_zscore(spread, window=window)
    current_z = float(zscore.dropna().iloc[-1])

    # Current OLS weights fitted on the most recent window
    coefs, _, _ = fit_basket(etf_aligned.iloc[-window:], constituent_df.iloc[-window:])
    coefs_floored = [max(0.0, c) for c in coefs]
    coef_sum = sum(coefs_floored)

    if vol_target > 0:
        import math as _math
        sv_series = spread.rolling(30).std().dropna()
        if len(sv_series) > 0:
            spread_vol = float(sv_series.iloc[-1]) * _math.sqrt(252)
            raw_notional = capital * vol_target / spread_vol if spread_vol > 1e-8 else capital
            half_notional = min(raw_notional, capital) / 2
        else:
            half_notional = capital / 2
        print(f"Vol target: {vol_target:.0%}  spread_vol: {spread_vol:.2%}  notional: ${half_notional*2:,.0f}")
    else:
        half_notional = capital / 2

    etf_notional = half_notional
    stock_notionals = {
        s: (coefs_floored[i] / coef_sum) * half_notional
        for i, s in enumerate(stocks)
        if coefs_floored[i] > 0
    }

    # Detect current position from Alpaca
    try:
        from src.trading.alpaca_trader import get_positions
        current_positions = get_positions()
    except Exception as e:
        if execute:
            print(f"ERROR: Could not fetch positions from Alpaca: {e}")
            print("  Aborting — cannot determine if already invested.")
            return
        current_positions = {}
        print(f"WARNING: Could not fetch positions: {e}")

    etf_pos = current_positions.get(etf, 0.0)
    in_short_spread = etf_pos < -50
    in_long_spread  = etf_pos >  50

    # Fallback: if the ETF leg didn't register (e.g. short-sell not available on paper)
    # but constituent stocks are substantially invested, we're already in this trade.
    stock_notional_invested = sum(abs(current_positions.get(s, 0.0)) for s in stocks)
    if not (in_short_spread or in_long_spread) and stock_notional_invested > 500:
        net_stock_pos   = sum(current_positions.get(s, 0.0) for s in stocks)
        in_short_spread = net_stock_pos > 0   # bought stocks → short-spread trade
        in_long_spread  = net_stock_pos < 0   # shorted stocks → long-spread trade

    in_position = in_short_spread or in_long_spread
    state_str   = "short spread" if in_short_spread else "long spread" if in_long_spread else "flat"

    # Latest ETF price for whole-share calculation (short sells require qty, not notional)
    etf_price  = float(etf_aligned.iloc[-1])
    etf_shares = max(1, int(etf_notional / etf_price))

    print(f"\nBasket:    {etf} vs [{', '.join(stocks)}]")
    print(f"Z-score:   {current_z:+.2f}  (entry ±{z_entry}  exit ±{z_exit}  stop ±{z_stop})")
    print(f"Position:  {state_str}")

    # Each order is one of:
    #   {"symbol", "side", "notional", "note"}        → notional market order (buys/long-close)
    #   {"symbol", "side", "qty",      "note"}        → whole-share order (ETF short sells)
    #   {"symbol", "close_pos": True,  "note"}        → close the full existing position
    orders = []

    # Time stop: close if position held too long regardless of z-score
    time_stopped = False
    if in_position and max_hold_days > 0:
        try:
            from src.trading.alpaca_trader import get_position_details
            from datetime import date as _date
            pos_details = get_position_details()
            etf_detail  = pos_details.get(etf, {})
            created_at  = etf_detail.get("created_at")
            if created_at is not None:
                created_date = created_at.date() if hasattr(created_at, "date") else created_at
                hold_days    = (_date.today() - created_date).days
                if hold_days >= max_hold_days:
                    time_stopped = True
                    print(f"Signal:    TIME STOP (held {hold_days}d >= {max_hold_days}d)")
                    for sym in [etf] + stocks:
                        if abs(current_positions.get(sym, 0.0)) > 10:
                            orders.append({"symbol": sym, "close_pos": True,
                                           "note": f"time-stop close {sym}"})
        except Exception as exc:
            print(f"  Time stop check failed: {exc}")

    if not time_stopped:
        if in_position:
            exit_triggered = abs(current_z) < z_exit
            stop_triggered = (in_short_spread and current_z < -z_stop) or \
                             (in_long_spread  and current_z >  z_stop)
            if exit_triggered or stop_triggered:
                reason = "stop-loss" if stop_triggered else "z-exit"
                print(f"Signal:    EXIT ({reason})")
                for sym in [etf] + stocks:
                    if abs(current_positions.get(sym, 0.0)) > 10:
                        orders.append({"symbol": sym, "close_pos": True, "note": f"close {sym}"})
            else:
                print(f"Signal:    HOLD")
        else:
            # VIX filter — block new entries during market stress
            vix_blocked = False
            if vix_filter > 0:
                try:
                    from src.data.fetcher import fetch_price
                    vix_today = float(fetch_price("^VIX", period="5d").dropna().iloc[-1])
                    print(f"VIX:       {vix_today:.1f}  (filter: >{vix_filter})")
                    if vix_today > vix_filter:
                        vix_blocked = True
                        print(f"Signal:    BLOCKED (VIX={vix_today:.1f} > {vix_filter})")
                except Exception as exc:
                    print(f"  VIX check failed: {exc}")

            if not vix_blocked:
                if len(stock_notionals) < 3:
                    print(f"Signal:    BLOCKED ({len(stock_notionals)} stocks survive OLS floor, need >= 3)")
                elif current_z > z_entry:
                    print(f"Signal:    SHORT SPREAD (ETF expensive)")
                    # ETF short requires whole shares — fractional short-sell is not supported
                    orders.append({"symbol": etf, "side": OrderSide.SELL, "qty": etf_shares,
                                   "notional": etf_notional, "note": f"short ETF ({etf_shares} shs)"})
                    for s, n in stock_notionals.items():
                        orders.append({"symbol": s, "side": OrderSide.BUY, "notional": n,
                                       "note": "long stock"})
                elif current_z < -z_entry:
                    print(f"Signal:    LONG SPREAD (ETF cheap)")
                    orders.append({"symbol": etf, "side": OrderSide.BUY, "notional": etf_notional,
                                   "note": "long ETF"})
                    # Stock short sells require whole shares — fractional short-sell is not supported
                    stock_prices = constituent_df.iloc[-1]
                    for s, n in stock_notionals.items():
                        s_shares = max(1, int(n / float(stock_prices[s])))
                        orders.append({"symbol": s, "side": OrderSide.SELL, "qty": s_shares,
                                       "notional": n, "note": f"short stock ({s_shares} shs)"})
                else:
                    print(f"Signal:    FLAT (waiting for |z| > {z_entry})")

    print(f"\n  {'Symbol':<8} {'Side':<6} {'Amount':>12}  Note")
    print(f"  {'-'*8} {'-'*6} {'-'*12}  {'-'*25}")
    for o in orders:
        if o.get("close_pos"):
            amt = f"{'(close all)':>12}"
            side_str = "close"
        elif o.get("qty") is not None:
            amt = f"{o['qty']:>9} shs"
            side_str = o["side"].value
        else:
            amt = f"${o['notional']:>9,.0f}  "
            side_str = o["side"].value
        print(f"  {o['symbol']:<8} {side_str:<6} {amt}  {o['note']}")
    if not orders:
        print("  (no orders)")

    if execute and orders:
        print(f"\nPlacing {len(orders)} order(s)...")
        for o in orders:
            try:
                if o.get("close_pos"):
                    close_position(o["symbol"])
                    print(f"  close {o['symbol']} — submitted")
                elif o.get("qty") is not None:
                    place_qty_order(o["symbol"], o["qty"], o["side"])
                    print(f"  {o['side'].value} {o['symbol']} {o['qty']} shs — submitted")
                else:
                    place_notional_order(o["symbol"], o["notional"], o["side"])
                    print(f"  {o['side'].value} {o['symbol']} ${o['notional']:,.0f} — submitted")
            except Exception as e:
                print(f"  ERROR on {o['symbol']}: {e}")
        print("Done.")
    elif orders:
        print("\nDry run — pass --execute to place orders.")


def _run_trade(args):
    from src.data.fetcher import fetch_prices_bulk
    from src.analytics.cta import vol_targeted_weights
    from src.strategies.cta.signals import CTA_UNIVERSE, generate_cta_positions
    from src.trading.alpaca_trader import (
        get_account, get_positions, place_notional_order, close_all_positions,
    )
    from src.trading.rebalancer import weights_to_orders

    if args.liquidate:
        print("Closing all positions...")
        close_all_positions()
        print("All positions closed.")
        return

    # Account info (required for --execute; optional for dry-run)
    acct = None
    try:
        acct = get_account()
        print(f"Account: equity=${acct['equity']:,.0f}  buying_power=${acct['buying_power']:,.0f}")
    except Exception as e:
        if args.execute or args.liquidate:
            print(f"ERROR: Could not connect to Alpaca: {e}")
            return
        print(f"(Alpaca account unavailable -- showing signal preview only)")

    capital = args.capital if args.capital > 0 else (acct["equity"] if acct else 20_000.0)

    if args.strategy == "basket":
        _run_trade_basket(args, acct, capital, execute=args.execute)
        return

    # Fetch prices — use Alpaca if keys available, else yfinance
    tickers = CTA_UNIVERSE["default"]
    import os as _os
    has_keys = bool(_os.environ.get("ALPACA_API_KEY") and _os.environ.get("ALPACA_SECRET_KEY"))
    provider = "alpaca" if has_keys else "yfinance"
    print(f"Fetching {len(tickers)} tickers (2y, provider={provider})...")
    try:
        prices_dict = fetch_prices_bulk(tickers, period="2y", provider=provider)
    except PermissionError as e:
        print(f"ERROR: {e}")
        return

    if len(prices_dict) < 2:
        print("ERROR: Not enough price data returned.")
        return

    prices_df = pd.DataFrame(prices_dict)
    prices_df = prices_df.dropna(thresh=int(0.80 * len(prices_df)), axis=1).dropna()
    print(f"Aligned {prices_df.shape[1]} instruments over {len(prices_df)} bars.")

    # Regime filter (optional)
    spy_prices = None
    if args.regime_filter and "SPY" in prices_df.columns:
        spy_prices = prices_df["SPY"]
        print("Regime filter: SPY 200-day MA active...")

    # Compute signals + weights (identical to _run_cta)
    signal_date = prices_df.index[-1].date()
    print(f"Computing signals ({signal_date})...")
    positions_df, _ = generate_cta_positions(
        prices_df, threshold=0.0, signal_mode="binary", spy_prices=spy_prices,
    )
    weights_df = vol_targeted_weights(
        positions_df, prices_df, tau=0.20, vol_span=args.vol_span,
    )

    target_weights  = weights_df.iloc[-1]
    current_prices  = prices_df.iloc[-1]
    try:
        current_positions = get_positions()
    except Exception:
        current_positions = {}

    orders = weights_to_orders(
        target_weights, current_prices, capital, current_positions,
        min_order_dollars=args.min_order,
    )

    # Print order table
    print(f"\n  {'Symbol':<8} {'Target%':>8} {'Current%':>9} {'Order $':>10}  Side")
    print(f"  {'-'*8} {'-'*8} {'-'*9} {'-'*10}  {'-'*4}")
    for o in orders:
        sign = "+" if o["order_notional"] > 0 else ""
        print(f"  {o['symbol']:<8} {o['target_pct']:>+8.1%} {o['current_pct']:>+9.1%} "
              f"  {sign}{o['order_notional']:>8,.0f}  {o['side'].value}")

    if not orders:
        print("  (no orders needed — already at target weights)")

    if args.execute:
        print(f"\nPlacing {len(orders)} order(s)...")
        for o in orders:
            try:
                place_notional_order(o["symbol"], abs(o["order_notional"]), o["side"])
                print(f"  {o['side'].value} {o['symbol']} ${abs(o['order_notional']):,.0f} — submitted")
            except Exception as e:
                print(f"  ERROR on {o['symbol']}: {e}")
        print("Done.")
    else:
        print("\nDry run — pass --execute to place orders.")


def _register_trade(subparsers):
    parser = subparsers.add_parser(
        "trade",
        help="Generate CTA signals and place paper orders via Alpaca",
    )
    parser.add_argument("--strategy", default="cta", choices=["cta", "basket"],
                        help="Strategy to trade (default: cta)")
    parser.add_argument("--capital", default=0.0, type=float, metavar="DOLLARS",
                        help="Portfolio capital in dollars (default: 0 = use account equity)")
    parser.add_argument("--min-order", default=50.0, type=float, metavar="DOLLARS",
                        dest="min_order",
                        help="Minimum order size in dollars — skip smaller rebalances (default: 50)")
    parser.add_argument("--vol-span", default=60, type=int, metavar="N",
                        dest="vol_span",
                        help="EWM span for vol estimation (default: 60)")
    parser.add_argument("--regime-filter", action="store_true", dest="regime_filter",
                        help="Suppress long equity positions when SPY is below its 200-day MA")
    parser.add_argument("--execute", action="store_true",
                        help="Place orders (default: dry-run preview only)")
    parser.add_argument("--liquidate", action="store_true",
                        help="Close all open positions and exit")
    # Basket-specific args (only used when --strategy basket)
    parser.add_argument("--etf", default=None, metavar="TICKER",
                        help="ETF ticker for basket strategy, e.g. XLF")
    parser.add_argument("--stocks", default=None, nargs="+", metavar="TICKER",
                        help="Constituent tickers (static mode). Omit to use EDGAR N-PORT top-N.")
    parser.add_argument("--static", action="store_true", dest="static_constituents",
                        help="Use fixed --stocks instead of live EDGAR N-PORT lookup.")
    parser.add_argument("--top-n", default=5, type=int, dest="top_n", metavar="N",
                        help="Number of top holdings to fetch from EDGAR N-PORT (default: 5).")
    parser.add_argument("--window", default=60, type=int, metavar="N",
                        help="OLS rolling window in days (default: 60)")
    parser.add_argument("--z-entry", default=1.5, type=float, dest="z_entry",
                        help="Z-score entry threshold (default: 1.5)")
    parser.add_argument("--z-exit", default=0.25, type=float, dest="z_exit",
                        help="Z-score exit threshold (default: 0.25)")
    parser.add_argument("--z-stop", default=2.5, type=float, dest="z_stop",
                        help="Z-score stop-loss threshold (default: 2.5)")
    parser.add_argument("--vix-filter", default=0.0, type=float, metavar="LEVEL", dest="vix_filter",
                        help="Suppress new basket entries when VIX > LEVEL (0 = off, e.g. 25).")
    parser.add_argument("--max-hold-days", default=0, type=int, metavar="N", dest="max_hold_days",
                        help="Force-close basket positions held longer than N days (0 = off).")
    parser.add_argument("--vol-target", default=0.0, type=float, metavar="F", dest="vol_target",
                        help="Annualised spread vol target as fraction of capital (0 = off, e.g. 0.10).")
    parser.set_defaults(func=_run_trade)


def main():
    parser = argparse.ArgumentParser(description="Quant Trading CLI")
    subparsers = parser.add_subparsers(dest="strategy", metavar="STRATEGY")
    subparsers.required = True

    _register_pairs(subparsers)
    _register_pca(subparsers)
    _register_basket(subparsers)
    _register_basket_multi(subparsers)
    _register_basket_history(subparsers)
    _register_cta(subparsers)
    _register_portfolio(subparsers)
    _register_trade(subparsers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

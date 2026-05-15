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
    compute_kalman_hedge_ratio, compute_kalman_spread,
)
from src.strategies.pairs.viz import (
    plot_all_dashboard, plot_pair_charts, plot_pair_interpretation,
    plot_pair_stats, plot_scan_results,
)


def _show(fig, title: str, static: bool = False) -> None:
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
                      kalman_delta=args.kalman_delta,
                      max_hold_days=args.max_hold_days,
                      dollar_stop_pct=args.dollar_stop,
                      test_period=args.test_period)


_PERIOD_BARS = {
    "3mo": 63, "6mo": 126, "1y": 252, "2y": 504, "5y": 1260, "10y": 2520,
}


def _pairs_single(
    ticker_a, ticker_b, period, window, z_entry, z_exit, z_stop,
    backtest=False, kalman_delta=1e-4,
    max_hold_days=0, dollar_stop_pct=5.0,
    test_period=None,
):
    print(f"Fetching {ticker_a}/{ticker_b}...")

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

    if backtest:
        from src.data.fetcher import fetch_pair_ohlcv
        from src.strategies.pairs.backtest import run_pairs_backtest
        from src.strategies.pairs.viz import (
            plot_equity_curve, plot_trade_pnl, plot_backtest_metrics,
            plot_backtest_interpretation,
        )
        print("Running backtest...")
        from src.analytics.market_beta import compute_market_beta
        df_ohlcv = fetch_pair_ohlcv(ticker_a, ticker_b, period=period)
        df_ohlcv = df_ohlcv.loc[df_ohlcv.index.isin(spread.index)]
        try:
            spy = fetch_price("SPY", period=period)
            market_beta_a = compute_market_beta(df_ohlcv["close_a"], spy)
            market_beta_b = compute_market_beta(df_ohlcv["close_b"], spy)
            print(f"Market betas at last bar — {ticker_a}: {market_beta_a.iloc[-1]:.2f}  {ticker_b}: {market_beta_b.iloc[-1]:.2f}")
        except Exception:
            market_beta_a = market_beta_b = None

        # Restrict backtest execution to the test window only
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
    parser.add_argument("--max-hold-days", type=int, default=0, metavar="N",
                        help="Time stop: close trade if still open after N days (default: 0 = auto, 3× half-life).")
    parser.add_argument("--dollar-stop", type=float, default=5.0, metavar="PCT",
                        help="Dollar stop: close trade if unrealised loss exceeds PCT%% of capital (default: 5.0). "
                             "Set to 0 to disable.")
    parser.set_defaults(func=_run_pairs)


def _run_pca(args):
    from src.data.fetcher import fetch_prices_bulk
    from src.analytics.pca import rolling_pca_residuals
    from src.strategies.pca.signals import generate_pca_signals
    from src.strategies.pca.viz import plot_pca_equity, plot_pca_zscore_heatmap, plot_pca_positions
    from src.backtest.portfolio_engine import run_portfolio_backtest

    universe_name = args.universe.lower()
    if universe_name not in SCAN_UNIVERSES:
        print(f"ERROR: Unknown universe '{args.universe}'. Available: {', '.join(SCAN_UNIVERSES)}")
        sys.exit(1)

    tickers = SCAN_UNIVERSES[universe_name]
    period  = args.period
    window  = args.window

    print(f"Fetching {len(tickers)} tickers ({period})...")
    prices_dict = fetch_prices_bulk(tickers, period=period)
    if len(prices_dict) < 3:
        print("ERROR: Need at least 3 tickers with data.")
        sys.exit(1)

    prices_df = pd.DataFrame(prices_dict).dropna()
    print(f"Aligned {prices_df.shape[1]} tickers over {len(prices_df)} bars.")

    returns_df = prices_df.pct_change().dropna()

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

    params = {
        "period": period, "window": window,
        "n_factors": args.n_factors, "top_n": args.top_n,
        "z_entry": args.z_entry, "z_exit": args.z_exit, "z_stop": args.z_stop,
        "cost_bps": args.cost_bps, "test_period": test_period,
    }
    universe_label = universe_name.capitalize()

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
    parser.set_defaults(func=_run_pca)


def _run_basket(args):
    from src.data.fetcher import fetch_price
    from src.analytics.stationarity import adf_test, compute_half_life
    from src.analytics.basket import rolling_basket_spread
    from src.strategies.basket.signals import generate_basket_signals
    from src.strategies.basket.backtest import run_basket_backtest
    from src.strategies.basket.viz import plot_basket_spread
    from src.strategies.pairs.viz import (
        plot_equity_curve, plot_trade_pnl, plot_backtest_metrics,
    )

    etf    = args.etf.upper()
    stocks = [s.strip().upper() for s in args.stocks]
    period = args.period
    window = args.window

    print(f"Fetching {etf} + {len(stocks)} constituent(s) ({period})...")
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

    # ── Train/test split ──────────────────────────────────────────────────────
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

    print(f"Computing rolling basket spread (window={window})...")
    spread = rolling_basket_spread(etf_aligned, constituent_prices, window=window)

    spread_for_calib = spread.iloc[:len(spread) - _PERIOD_BARS.get(test_period, 0)] \
        if test_period else spread
    spread_clean = spread_for_calib.dropna()

    adf = adf_test(spread_clean)
    hl  = compute_half_life(spread_clean)
    hl_str = f"{hl:.1f} days" if hl != float("inf") else "inf"
    print(
        f"Spread ADF p-val: {adf['p_value']:.4f}  "
        f"({'stationary' if adf['is_stationary'] else 'non-stationary'})  "
        f"Half-life: {hl_str}"
    )

    print("Generating signals...")
    signals, zscore = generate_basket_signals(
        spread, window=window,
        z_entry=args.z_entry, z_exit=args.z_exit, z_stop=args.z_stop,
    )

    params = {
        "period": period, "window": window,
        "z_entry": args.z_entry, "z_exit": args.z_exit, "z_stop": args.z_stop,
        "test_period": test_period,
    }

    if split_date is not None:
        signals_bt = signals.loc[signals.index >= split_date]
        spread_bt  = spread.loc[spread.index >= split_date]
        print(f"Backtesting on test period ({split_date.date()} to {signals.index[-1].date()})")
    else:
        signals_bt, spread_bt = signals, spread

    print("Running backtest...")
    trades, equity_curve, bt_metrics = run_basket_backtest(
        signals_bt, spread_bt, capital=20_000.0, cost_bps=args.cost_bps,
    )

    period_label = f"({test_period} test)" if test_period else ""
    print(
        f"Basket {period_label}: {bt_metrics['n_trades']} trades  |  "
        f"{bt_metrics['total_return']:.1%} return  |  "
        f"Sharpe {bt_metrics['sharpe']:.2f}"
    )

    print("Opening windows...")
    _show(
        plot_basket_spread(spread, zscore, signals, etf, stocks, params, split_date=split_date),
        f"Basket — {etf} — Spread",
    )
    if not trades.empty:
        _show(plot_equity_curve(equity_curve, trades, etf, "BASKET", 20_000.0),
              f"Basket — {etf} — Equity")
        _show(plot_trade_pnl(trades, etf, "BASKET"),
              f"Basket — {etf} — Trade P&L")
        _show(plot_backtest_metrics(bt_metrics, trades, etf, "BASKET", params),
              f"Basket — {etf} — Metrics")


def _run_basket_multi(args):
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
    n_folds       = getattr(args, "walk_forward", None)
    total_capital = 20_000.0
    leg_capital   = total_capital / len(baskets)
    fold_bars     = 252  # 1 year per fold

    params = {
        "period": period, "window": window,
        "z_entry": args.z_entry, "z_exit": args.z_exit, "z_stop": args.z_stop,
        "cost_bps": args.cost_bps, "test_period": test_period,
    }

    print(
        "\nNOTE: constituents are fixed at today's composition. "
        "Survivorship bias may inflate returns — stocks that were delisted or "
        "removed from the ETF during the backtest period are excluded."
    )

    # ---- Phase 1: Fetch data and compute signals for all baskets ----
    basket_data = []  # (label, spread, signals, n_stocks)

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
        )

        basket_data.append((label, spread, signals, constituent_prices.shape[1]))

    if not basket_data:
        print("ERROR: No baskets ran successfully.")
        sys.exit(1)

    # ---- Phase 2a: Walk-forward (N non-overlapping 1y OOS folds) ----
    if n_folds:
        print(f"\nRunning walk-forward validation ({n_folds} folds x 1y)...")

        fold_combined_metrics = []
        all_stitched_pnls     = []

        for fold_k in range(n_folds):
            # fold_k=0 is the oldest window; fold_k=n_folds-1 is the most recent
            fold_leg_pnls  = []
            fold_n_trades  = 0
            fold_win_rates = []

            for label, spread, signals, n_stocks_leg in basket_data:
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
                )
                fold_n_trades += mf.get("n_trades", 0)
                wr = mf.get("win_rate")
                if wr is not None and not (isinstance(wr, float) and _math.isnan(wr)):
                    fold_win_rates.append(wr)

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
            f"Walk-Forward -- {' + '.join(lb for lb, _, _, _ in basket_data)}",
        )
        return

    # ---- Phase 2b: Single OOS mode (existing behaviour) ----
    leg_equities = {}
    leg_metrics  = {}
    daily_pnls   = []

    for label, spread, signals, n_stocks_leg in basket_data:
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
        )
        n_t = metrics.get("n_trades", 0)
        ret = metrics.get("total_return", 0.0)
        sh  = metrics.get("sharpe", 0.0)
        print(f"  {label}: {n_t} trades  |  {ret:.1%} return  |  Sharpe {sh:.2f}")

        leg_equities[label] = equity_curve
        leg_metrics[label]  = metrics

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
    parser.add_argument("--walk-forward", default=None, type=int, metavar="N",
                        dest="walk_forward",
                        help="Walk-forward validation: run N non-overlapping 1-year OOS folds "
                             "(requires --period >= N+1 years). Overrides --test-period.")
    parser.add_argument("--ridge-alpha", default=0.0, type=float, metavar="A",
                        dest="ridge_alpha",
                        help="Ridge (L2) regularisation for OLS basket fit (default: 0 = off). "
                             "Reduces overfitting when n_stocks/window is high. Try 0.05–0.20.")
    parser.add_argument("--regime-filter", default=0.0, type=float, metavar="T",
                        dest="regime_filter",
                        help="Suppress spread when normalised OLS coefficient shift exceeds T "
                             "(default: 0 = off). Detects structural breaks. Try 0.20–0.50.")
    parser.set_defaults(func=_run_basket_multi)


def _register_basket(subparsers):
    parser = subparsers.add_parser("basket", help="Basket / ETF arbitrage")
    parser.add_argument("--etf",     required=True, metavar="TICKER",
                        help="ETF ticker to trade against the basket, e.g. XLF")
    parser.add_argument("--stocks",  required=True, nargs="+", metavar="TICKER",
                        help="Constituent tickers, e.g. GS MS JPM BAC C")
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
    from src.data.fetcher import fetch_prices_bulk
    from src.analytics.cta import vol_targeted_weights
    from src.strategies.cta.signals import CTA_UNIVERSE, generate_cta_positions
    from src.strategies.cta.viz import plot_cta_equity, plot_cta_signals, plot_cta_contributions
    from src.backtest.portfolio_engine import run_portfolio_backtest

    universe_name = args.universe.lower()
    if universe_name not in CTA_UNIVERSE:
        print(f"ERROR: Unknown universe '{args.universe}'. Available: {', '.join(CTA_UNIVERSE)}")
        sys.exit(1)

    tickers = CTA_UNIVERSE[universe_name]
    period  = args.period

    print(f"Fetching {len(tickers)} tickers ({period})...")
    prices_dict = fetch_prices_bulk(tickers, period=period)
    if len(prices_dict) < 2:
        print("ERROR: Need at least 2 tickers with data.")
        sys.exit(1)

    prices_df = pd.DataFrame(prices_dict)

    # Drop tickers with < 80% coverage before aligning
    min_obs = int(0.80 * len(prices_df))
    prices_df = prices_df.dropna(thresh=min_obs, axis=1)
    prices_df = prices_df.dropna()

    n_instruments = prices_df.shape[1]
    dropped = len(prices_dict) - n_instruments
    if dropped:
        print(f"  Dropped {dropped} ticker(s) with insufficient history.")
    print(f"Aligned {n_instruments} instruments over {len(prices_df)} bars.")

    # ── Train/test split ──────────────────────────────────────────────────────
    split_date  = None
    test_period = args.test_period
    if test_period:
        n_test = _PERIOD_BARS.get(test_period, 252)
        # Need enough warm-up for the slowest EMA (256 bars) before split
        if n_test >= len(prices_df) - 300:
            print(f"WARNING: --test-period '{test_period}' leaves too little data. Ignoring.")
            test_period = None
        else:
            split_idx  = len(prices_df) - n_test
            split_date = prices_df.index[split_idx]
            print(f"Train/test split — training up to {split_date.date()}  |  test: {test_period} forward")

    pairs = ((8, 32), (16, 64), (32, 128), (64, 256))

    # Signals use only past prices at every bar — no fitting step, no leakage
    print("Computing EWMAC signals...")
    positions_df, signals_df = generate_cta_positions(prices_df, pairs=pairs, threshold=args.threshold)

    # Vol-targeted weights computed on full history for proper EWM warm-up, then sliced
    weight_cap = args.weight_cap if args.weight_cap > 0 else None
    print(f"Applying vol targeting (tau={args.vol_target:.0%}, cap={weight_cap or 'none'})...")
    weights_df = vol_targeted_weights(
        positions_df, prices_df,
        tau=args.vol_target,
        weight_cap=weight_cap,
    )

    # Restrict backtest to test window if set
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

    print(f"Running portfolio backtest ({n_instruments} instruments, cost={args.cost_bps}bps)...")
    equity_curve, bt_metrics = run_portfolio_backtest(
        positions_bt, prices_bt, capital=args.capital, cost_bps=args.cost_bps,
        weights_df=weights_bt,
    )

    period_label = f"({test_period} test)" if test_period else f"({period} full)"
    print(
        f"CTA Trend Following {period_label}: "
        f"{bt_metrics['total_return']:.1%} return  |  "
        f"Sharpe {bt_metrics['sharpe']:.2f}  |  "
        f"Max DD {bt_metrics['max_drawdown']:.1%}"
    )

    params = {
        "period": period,
        "n_instruments": n_instruments,
        "vol_target": f"{args.vol_target:.0%}",
        "threshold": args.threshold,
        "cost_bps": args.cost_bps,
        "test_period": test_period,
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
    parser.add_argument("--threshold", default=0.0, type=float, metavar="T",
                        help="Signal flat-band: |EWMAC| must exceed T to enter a position (default: 0)")
    parser.add_argument("--vol-target", default=0.20, type=float, metavar="TAU",
                        dest="vol_target",
                        help="Annualised portfolio vol target for position sizing (default: 0.20 = 20%%). "
                             "Each instrument's weight = direction × tau / (sigma_i × N_active).")
    parser.add_argument("--weight-cap", default=0.0, type=float, metavar="W",
                        dest="weight_cap",
                        help="Per-instrument weight cap as fraction of capital (default: 0 = no cap). "
                             "E.g. 0.40 limits any single instrument to ±40%% of capital.")
    parser.add_argument("--cost-bps",  default=5.0, type=float, metavar="BPS",
                        help="Transaction cost per unit of portfolio turnover in bps (default: 5)")
    parser.add_argument("--capital",   default=20_000.0, type=float, metavar="DOLLARS",
                        help="Starting capital (default: 20000)")
    parser.set_defaults(func=_run_cta)


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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

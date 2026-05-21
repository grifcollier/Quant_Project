"""
Generate the project documentation PDF.
Run: python generate_docs.py
Output: docs/Quant_Project_Guide.pdf
"""

from fpdf import FPDF
from pathlib import Path
import datetime

OUT_DIR = Path("docs")
OUT_DIR.mkdir(exist_ok=True)
OUT_PATH = OUT_DIR / "Quant_Project_Guide.pdf"

# ?? Colours ??????????????????????????????????????????????????????????????????
C_DARK   = (26,  37,  47)
C_MID    = (44,  62,  80)
C_ACCENT = (31, 119, 180)
C_GREEN  = (44, 160,  44)
C_LIGHT  = (244,246,248)
C_WHITE  = (255,255,255)
C_CODE   = (240,240,240)
C_BORDER = (200,200,200)

# ?? PDF class ?????????????????????????????????????????????????????????????????
class Doc(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 20, 20)
        self._toc = []          # (level, title, page)
        self._section_num = 0

    # ?? Header / footer ??????????????????????????????????????????????????????
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*C_MID)
        self.cell(0, 6, "Quant Project  -  Developer & User Guide", align="L")
        self.cell(0, 6, f"Page {self.page_no()}", align="R")
        self.ln(2)
        self.set_draw_color(*C_BORDER)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(3)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*C_BORDER)
        self.cell(0, 5, f"Generated {datetime.date.today().isoformat()}", align="C")

    # ?? Typography helpers ????????????????????????????????????????????????????
    def h1(self, text):
        self._section_num += 1
        self._toc.append((1, f"{self._section_num}. {text}", self.page_no()))
        self.ln(4)
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, f"  {self._section_num}.  {text}", fill=True, ln=True)
        self.set_text_color(*C_MID)
        self.ln(3)

    def h2(self, text):
        self._toc.append((2, f"    {text}", self.page_no()))
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*C_ACCENT)
        self.cell(0, 7, text, ln=True)
        self.set_draw_color(*C_ACCENT)
        self.line(20, self.get_y(), 100, self.get_y())
        self.set_text_color(*C_MID)
        self.ln(3)

    def h3(self, text):
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*C_MID)
        self.cell(0, 6, text, ln=True)
        self.ln(1)

    def body(self, text):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*C_MID)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text, indent=5):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*C_MID)
        self.set_x(20 + indent)
        self.cell(4, 5.5, "-")
        self.multi_cell(0, 5.5, text)

    def code(self, text, label=None):
        if label:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 4, label, ln=True)
        self.set_fill_color(*C_CODE)
        self.set_draw_color(*C_BORDER)
        self.set_font("Courier", "", 8)
        self.set_text_color(40, 40, 40)
        lines = text.strip().split("\n")
        pad = 3
        self.rect(20, self.get_y(), 170, pad + len(lines) * 4.2 + pad, style="DF")
        self.set_x(20 + pad)
        self.ln(pad)
        for line in lines:
            self.set_x(20 + pad)
            self.cell(0, 4.2, line, ln=True)
        self.ln(pad)
        self.set_text_color(*C_MID)

    def kv_table(self, rows, col1_w=55):
        self.set_font("Helvetica", "", 9)
        fill = False
        usable = self.w - self.l_margin - self.r_margin
        val_w = usable - col1_w
        for k, v in rows:
            self.set_fill_color(*(C_LIGHT if fill else C_WHITE))
            self.set_draw_color(*C_BORDER)
            self.set_font("Helvetica", "B", 9)
            self.cell(col1_w, 6, k, border=1, fill=True)
            self.set_font("Helvetica", "", 9)
            self.multi_cell(val_w, 6, v, border=1, fill=True)
            fill = not fill
        self.ln(2)

    def param_table(self, headers, rows):
        self.set_font("Helvetica", "B", 8.5)
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_WHITE)
        col_w = 170 // len(headers)
        for h in headers:
            self.cell(col_w, 6, h, border=1, fill=True)
        self.ln()
        self.set_text_color(*C_MID)
        fill = False
        for row in rows:
            self.set_fill_color(*(C_LIGHT if fill else C_WHITE))
            self.set_font("Helvetica", "", 8.5)
            for i, cell in enumerate(row):
                self.cell(col_w, 5.5, str(cell), border=1, fill=True)
            self.ln()
            fill = not fill
        self.ln(2)


# ???????????????????????????????????????????????????????????????????????????????
# Build document
# ???????????????????????????????????????????????????????????????????????????????
def build(pdf: Doc):

    # ?? Cover page ????????????????????????????????????????????????????????????
    pdf.add_page()
    pdf.set_fill_color(*C_DARK)
    pdf.rect(0, 0, 210, 297, "F")

    pdf.set_y(60)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 14, "Quant Project", align="C", ln=True)

    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(150, 180, 210)
    pdf.cell(0, 10, "Developer & User Guide", align="C", ln=True)

    pdf.ln(8)
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(0.8)
    pdf.line(50, pdf.get_y(), 160, pdf.get_y())
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(180, 200, 220)
    strategies = [
        "Pairs Trading (Cointegration + Kalman Filter)",
        "PCA Statistical Arbitrage",
        "Basket / ETF Arbitrage",
        "CTA Trend Following (Multi-Horizon EWMAC)",
        "Multi-Strategy Portfolio",
        "Alpaca Paper Trading",
    ]
    for s in strategies:
        pdf.cell(0, 8, s, align="C", ln=True)

    pdf.set_y(240)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 130, 160)
    pdf.cell(0, 6, f"Generated {datetime.date.today().strftime('%B %d, %Y')}", align="C", ln=True)
    pdf.cell(0, 6, "Python 3.12  |  yfinance  |  Alpaca  |  Plotly  |  fpdf2", align="C", ln=True)

    # ?? Section 1: Project Overview ???????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Project Overview")

    pdf.body(
        "This project is a multi-strategy quantitative trading system built in Python. "
        "It implements four distinct trading strategies, a combined portfolio view, a "
        "parameter sweep diagnostic tool, walk-forward validation for out-of-sample testing, "
        "and a live paper trading interface via the Alpaca API. The project is structured "
        "as a command-line application driven by run.py, with modular analytics, strategy, "
        "backtest, data, and visualization layers."
    )

    pdf.h2("Design Philosophy")
    pdf.body(
        "The system is built around three principles: (1) No look-ahead bias  -  all signals "
        "are computed causally using only data available at the time of each bar. "
        "(2) Out-of-sample validation  -  every strategy supports walk-forward testing across "
        "non-overlapping time windows. (3) Separation of concerns  -  analytics functions are "
        "pure (no I/O), strategies call analytics, the CLI calls strategies."
    )

    pdf.h2("Strategy Summary")
    pdf.param_table(
        ["Subcommand", "Strategy", "Universe", "Signal Type"],
        [
            ["pairs", "Pairs Trading", "User-specified (e.g. GS/MS)", "Mean-reversion z-score"],
            ["pca", "PCA Stat Arb", "Named universe (e.g. energy)", "PCA residual z-score"],
            ["basket / basket-multi", "Basket Arbitrage", "ETF + constituents", "OLS spread z-score"],
            ["cta", "CTA Trend Following", "16 ETFs (4 asset classes)", "EWMAC crossover"],
            ["portfolio", "Combined Portfolio", "All strategies", "Equal-risk weighted"],
            ["trade", "Paper Trading", "CTA default universe", "Live CTA signal"],
        ]
    )

    pdf.h2("Key Performance Results (Walk-Forward OOS)")
    pdf.param_table(
        ["Strategy", "Universe", "Folds", "Avg Sharpe", "Total Return", "Max DD"],
        [
            ["CTA", "16 ETFs", "5 x 1y", "0.70", "+30.5%", "-15.3%"],
            ["PCA", "Energy sector", "3 x 1y", "+0.30", "+12.6% (fold 3)", "-21.5%"],
            ["Pairs", "GS/MS", "3 x 1y", "0.89 avg", "+3.0% avg/fold", "n/a"],
            ["PCA", "Tech sector", "3 x 1y", "-0.08", "Loses money OOS", "-30.9%"],
        ]
    )
    pdf.body(
        "Key finding: PCA only works OOS in the energy sector where stocks share a strong "
        "common factor (oil price). CTA benefits significantly from using vol_span=60 "
        "(slower vol estimation) vs the default 25."
    )

    # ?? Section 2: File Structure ?????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("File Structure & Architecture")

    pdf.code(
        "Quant_Project/\n"
        "  run.py                      # CLI entry point  -  all subcommands\n"
        "  generate_docs.py            # This script  -  regenerates the PDF\n"
        "  requirements.txt\n"
        "  pytest.ini\n"
        "  data/cache/                 # Auto-created CSV price cache\n"
        "  .cache/edgar/               # EDGAR filing cache\n"
        "  docs/                       # Generated PDF output\n"
        "  tests/\n"
        "    conftest.py               # Shared fixtures\n"
        "    test_cta_signals.py\n"
        "    test_portfolio_engine.py\n"
        "    test_analytics_cta.py\n"
        "  src/\n"
        "    analytics/                # Pure functions  -  no I/O\n"
        "      cta.py                  # EWMAC signals + vol targeting\n"
        "      pca.py                  # Rolling PCA residuals\n"
        "      basket.py               # OLS basket spread construction\n"
        "      cointegration.py        # ADF tests + universe scanner\n"
        "      stationarity.py         # ADF test + half-life estimation\n"
        "      market_beta.py          # Rolling beta + beta-neutral sizing\n"
        "      costs.py                # Kyle's lambda cost model\n"
        "    data/\n"
        "      fetcher.py              # yfinance price fetching + CSV cache\n"
        "      alpaca_fetcher.py       # Alpaca Market Data API fetcher\n"
        "      edgar.py                # SEC EDGAR N-PORT constituent history\n"
        "    strategies/\n"
        "      pairs/                  # Pairs trading\n"
        "        config.py             # Pair definitions + scan universes\n"
        "        spread.py             # OLS / Kalman hedge ratio + spread\n"
        "        signals.py            # Z-score + state-machine signals\n"
        "        backtest.py           # Trade log + pairs backtest runner\n"
        "        viz.py                # All pairs charts\n"
        "      pca/                    # PCA statistical arbitrage\n"
        "        signals.py            # PCA z-score signal generation\n"
        "        viz.py                # PCA equity + z-score charts\n"
        "      basket/                 # Basket / ETF arbitrage\n"
        "        signals.py            # Basket z-score signals\n"
        "        backtest.py           # Basket trade log + backtest\n"
        "        viz.py                # Basket charts\n"
        "      cta/                    # CTA trend following\n"
        "        signals.py            # EWMAC positions + regime filter\n"
        "        sweep.py              # Parameter grid search\n"
        "        viz.py                # CTA equity, sweep heatmap, walk-forward\n"
        "    backtest/\n"
        "      engine.py               # Trade-log to equity curve\n"
        "      metrics.py              # Performance metrics\n"
        "      portfolio_engine.py     # Daily mark-to-market portfolio backtest\n"
        "    trading/\n"
        "      alpaca_trader.py        # Alpaca TradingClient wrapper\n"
        "      rebalancer.py           # Weights to orders converter\n"
        "    viz/\n"
        "      theme.py                # Shared colour palette\n"
        "      portfolio.py            # Combined portfolio chart\n"
    )

    pdf.h2("Data Flow")
    pdf.body(
        "The system follows a strict unidirectional data flow: "
        "data/ fetches raw prices -> analytics/ computes signals -> "
        "strategies/ generate positions -> backtest/ produces equity curves -> "
        "viz/ renders charts. The CLI in run.py orchestrates this pipeline "
        "for each subcommand. The trading/ module connects the strategy output "
        "to live paper order execution."
    )

    # ?? Section 3: Data Layer ?????????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Data Layer")

    pdf.h2("src/data/fetcher.py  -  Price Data")
    pdf.body(
        "The primary price fetching module. All data is cached to data/cache/ as "
        "CSV files named {ticker}_{period}_{interval}.csv. Cached files are served "
        "on repeat runs, making the system fast after the first fetch."
    )
    pdf.h3("Key Functions")
    pdf.kv_table([
        ("fetch_price(ticker, period)", "Returns a pd.Series of closing prices for one ticker."),
        ("fetch_ohlcv(ticker, period)", "Returns a DataFrame with columns [open, high, low, close, volume]."),
        ("fetch_pair(a, b, period)", "Returns aligned close prices for two tickers as a DataFrame."),
        ("fetch_prices_bulk(tickers, period, provider)", "Fetches many tickers efficiently. provider='yfinance' (default) or 'alpaca'. Returns dict[ticker, Series]."),
        ("fetch_ohlcv_bulk(tickers, period, provider)", "Like fetch_prices_bulk but returns full OHLCV DataFrames. Used for volume-adjusted cost model."),
        ("fetch_pair_ohlcv(a, b, period)", "Fetches and aligns full OHLCV for a pair. Used by pairs backtest."),
    ])

    pdf.body(
        "Cache invalidation: if a cached file lacks the full OHLCV columns (legacy single-column "
        "cache), it is automatically re-fetched. The cache never expires automatically  -  "
        "delete data/cache/ to force a fresh download."
    )

    pdf.h2("src/data/alpaca_fetcher.py  -  Alpaca Market Data")
    pdf.body(
        "Alternative price data source using the Alpaca Market Data API. Requires live "
        "account API keys set as environment variables ALPACA_API_KEY and ALPACA_SECRET_KEY. "
        "Paper-only keys do NOT have data API access  -  live account keys are required."
    )
    pdf.h3("Key Functions")
    pdf.kv_table([
        ("fetch_prices_bulk_alpaca(tickers, period)", "Fetches closing prices from Alpaca. Returns same dict[ticker, Series] format as yfinance. Caches to data/cache/{ticker}_{period}_{interval}_alpaca.csv."),
        ("fetch_ohlcv_bulk_alpaca(tickers, period)", "Fetches full OHLCV DataFrames from Alpaca. Used when --cost-model volume-adjusted is combined with --data-provider alpaca."),
    ])
    pdf.body(
        "Error handling: A 401 Unauthorized error is caught and re-raised as a PermissionError "
        "with a clear message directing the user to use live account keys."
    )

    pdf.h2("src/data/edgar.py  -  SEC EDGAR Constituent History")
    pdf.body(
        "Downloads historical ETF constituent lists from SEC N-PORT-P filings. "
        "This is used to eliminate survivorship bias in basket strategy backtests  -  "
        "instead of using today's ETF composition for past periods, the actual holdings "
        "at each point in time are used."
    )
    pdf.body(
        "N-PORT-P was introduced in April 2019, so constituent history is only available "
        "from that date onwards. All filings and CUSIP-to-ticker mappings are cached "
        "in .cache/edgar/ to avoid repeated SEC API calls."
    )
    pdf.h3("Key Functions")
    pdf.kv_table([
        ("build_constituent_history(ticker, start, end)", "Fetches all N-PORT-P filings for an ETF between start and end dates. Returns DataFrame[filing_date, constituents, weights]."),
        ("get_constituents_at(history, date)", "Returns the constituent list from the most recent filing on or before the given date. Used for point-in-time lookups inside walk-forward folds."),
        ("resolve_cusips(cusips)", "Maps CUSIP identifiers to ticker symbols via the OpenFIGI API (free, no key required). Results are cached permanently."),
    ])
    pdf.body(
        "Trust-based ETFs (SPDR sector funds like XLF, XLK, XLE) share a single CIK "
        "and require series-level filtering. The _TRUST_ETF_MAP dictionary hardcodes "
        "the series IDs for 11 SPDR Select Sector ETFs."
    )

    # ?? Section 4: Analytics Layer ????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Analytics Layer")

    pdf.body(
        "All functions in src/analytics/ are pure  -  they take DataFrames and return "
        "DataFrames or Series. No file I/O, no plotting, no side effects. "
        "This makes them easy to test and compose."
    )

    pdf.h2("src/analytics/cta.py  -  EWMAC & Vol Targeting")

    pdf.h3("ewmac(prices, fast, slow)")
    pdf.body(
        "Computes the Exponentially Weighted Moving Average Crossover signal for a single "
        "price series. The signal measures whether the short-term trend is stronger than "
        "the long-term trend."
    )
    pdf.code(
        "signal = (EMA_fast - EMA_slow) / instrument_vol\n"
        "signal = clip(signal, -2, +2)"
    )
    pdf.body(
        "Dividing by instrument volatility normalises the signal so it is comparable "
        "across instruments and time periods. Capping at +/-2 prevents extreme values "
        "from dominating position sizing."
    )

    pdf.h3("combined_ewmac(prices, pairs)")
    pdf.body(
        "Averages EWMAC signals across multiple horizon pairs. The default pairs are "
        "(8,32), (16,64), (32,128), and (64,256)  -  representing roughly weekly, "
        "biweekly, monthly, and quarterly trends. Combining horizons gives a more "
        "robust signal than any single crossover."
    )

    pdf.h3("instrument_vol(prices, span)")
    pdf.body(
        "Computes annualised volatility using an Exponentially Weighted standard deviation "
        "of daily returns. Used to normalise EWMAC signals and size positions."
    )
    pdf.code("vol = EWM(span=span).std(daily_returns) * sqrt(252)")

    pdf.h3("vol_targeted_weights(positions_df, prices_df, tau, vol_span, weight_cap, corr_adjust)")
    pdf.body(
        "Converts direction signals (+/-1 or continuous) into portfolio weights that "
        "target a specified level of portfolio volatility (tau). This is the core "
        "position sizing function for the CTA strategy."
    )
    pdf.code(
        "# Base formula (per instrument, per bar):\n"
        "weight_i = direction_i x tau / (sigma_i x N_active)\n"
        "\n"
        "# With corr_adjust=True:\n"
        "# The base weights are scaled so the realized portfolio vol hits tau.\n"
        "port_vol = EWM(span=63).std(portfolio_returns) * sqrt(252)\n"
        "scale = clip(tau / port_vol, 0.5, 3.0)\n"
        "weights = base_weights x scale"
    )
    pdf.body(
        "Parameters: tau=0.20 means target 20% annualised portfolio volatility. "
        "weight_cap limits any single instrument to a fraction of capital. "
        "corr_adjust corrects for correlation concentration  -  when many instruments "
        "are highly correlated (e.g. all equity ETFs trending together), the base "
        "formula overallocates. The correction scales the whole portfolio down to "
        "keep realised vol near the target."
    )

    pdf.h2("src/analytics/pca.py  -  PCA Residuals")

    pdf.h3("rolling_pca_residuals(returns_df, window, n_components)")
    pdf.body(
        "Computes rolling out-of-sample PCA residuals. For each bar t, PCA is fitted "
        "on the previous 'window' days of returns. The current day's returns are then "
        "projected onto the fitted factor loadings, and the residuals (idiosyncratic "
        "returns not explained by the common factors) are returned."
    )
    pdf.body(
        "This is the key no-look-ahead step: the PCA model only uses past data at "
        "each point, so the residuals represent genuine out-of-sample idiosyncratic moves. "
        "The residuals are what the PCA strategy trades  -  they are expected to mean-revert "
        "since the common factors (market, sector) have been removed."
    )
    pdf.code(
        "# For each bar t (simplified):\n"
        "loadings = fit_pca(returns[t-window:t], n_components)\n"
        "residual[t] = returns[t] - loadings @ (loadings.T @ returns[t])"
    )

    pdf.h2("src/analytics/cointegration.py  -  Pair Testing")
    pdf.h3("scan_universe(tickers, prices, min_correlation)")
    pdf.body(
        "Scans all pairs within a universe for cointegration. First applies a "
        "correlation filter (default: r >= 0.80) to eliminate pairs unlikely to "
        "be cointegrated. Then for each remaining pair: computes the OLS hedge ratio, "
        "constructs the spread, runs the Augmented Dickey-Fuller test, and computes "
        "the half-life of mean reversion."
    )
    pdf.body(
        "A pair PASSES if: ADF p-value < 0.10 (spread is stationary) AND "
        "half-life is between 5 and 100 days (mean-reversion is fast enough to trade "
        "but slow enough to enter/exit without excessive slippage)."
    )

    pdf.h2("src/analytics/stationarity.py  -  Statistical Tests")
    pdf.kv_table([
        ("adf_test(spread)", "Augmented Dickey-Fuller test. Returns p-value and is_stationary flag (p < 0.10). Tests the null hypothesis that the spread has a unit root (is non-stationary / random walk)."),
        ("compute_half_life(spread)", "Fits an AR(1) model to the spread and derives the half-life from the mean-reversion coefficient. Half-life = -log(2) / log(1 + phi) where phi is the AR(1) coefficient."),
    ])

    pdf.h2("src/analytics/market_beta.py  -  Beta Neutrality")
    pdf.kv_table([
        ("compute_market_beta(stock, market, window)", "Rolling OLS regression of stock returns on market (SPY) returns. Returns a Series of rolling betas."),
        ("compute_beta_neutral_allocation(capital, beta_a, beta_b)", "Solves for capital allocations V_a and V_b such that the portfolio is simultaneously dollar-neutral (V_a = V_b) and beta-neutral (V_a * beta_a = V_b * beta_b)."),
    ])

    pdf.h2("src/analytics/costs.py  -  Transaction Cost Model")
    pdf.body(
        "Implements a volume-adjusted transaction cost model using a simplified "
        "Kyle's lambda approximation. More realistic than flat bps for strategies "
        "with varying liquidity across instruments."
    )
    pdf.code(
        "# One-way cost per bar:\n"
        "ADV_t = rolling(20).mean(volume x price)\n"
        "market_impact_t = 0.1 x daily_vol_t x sqrt(order_notional / ADV_t)\n"
        "cost_t = half_spread_bps + market_impact_t x 10,000"
    )
    pdf.body(
        "For liquid ETFs like SPY/QQQ this produces ~0.5-1.5 bps vs the flat 5 bps default. "
        "For less liquid single stocks it can reach 3-8 bps."
    )

    # ?? Section 5: Strategies ?????????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Strategies")

    pdf.h2("5.1  Pairs Trading")
    pdf.body(
        "Statistical arbitrage based on cointegration between two securities. When two "
        "stocks move together over time (cointegrated), temporary divergences from their "
        "long-run equilibrium represent trading opportunities. The strategy goes long "
        "the underperformer and short the outperformer, expecting convergence."
    )

    pdf.h3("Spread Construction (src/strategies/pairs/spread.py)")
    pdf.body("Three methods for computing the hedge ratio:")
    pdf.kv_table([
        ("Static OLS", "Single regression over the full period. Simple but the hedge ratio can drift. Use compute_hedge_ratio() and compute_spread()."),
        ("Rolling OLS", "Time-varying hedge ratio using a rolling regression window. More adaptive but introduces noise. Use compute_rolling_hedge_ratio()."),
        ("Kalman Filter (default)", "State-space model that tracks the hedge ratio in real time. Optimal for non-stationary relationships. Use compute_kalman_hedge_ratio() and compute_kalman_spread()."),
    ])
    pdf.body(
        "The Kalman filter is controlled by delta (process noise). Higher delta = faster "
        "adaptation to regime changes, lower delta = smoother but slower. Default 1e-4."
    )

    pdf.h3("Signal Generation (src/strategies/pairs/signals.py)")
    pdf.body(
        "A state machine that generates entry and exit signals from the z-score of the spread."
    )
    pdf.code(
        "z_score = (spread - rolling_mean(window)) / rolling_std(window)\n"
        "\n"
        "Entry:  long spread  when z < -z_entry  (spread too low, expect rise)\n"
        "        short spread when z > +z_entry  (spread too high, expect fall)\n"
        "Exit:   when |z| < z_exit              (spread reverted to mean)\n"
        "Stop:   when z > +z_stop (for long)    (spread moved further against us)\n"
        "        when z < -z_stop (for short)"
    )
    pdf.body("Default parameters: z_entry=2.0, z_exit=0.5, z_stop=3.0, window=auto (2.5x half-life).")

    pdf.h3("Backtest (src/strategies/pairs/backtest.py)")
    pdf.body(
        "Builds a trade log from signals and OHLCV prices. Uses close-to-close fills. "
        "Position sizing solves for dollar-neutral AND beta-neutral allocation simultaneously:"
    )
    pdf.code(
        "V_a = total_capital x beta_b / (beta_a + beta_b)\n"
        "V_b = total_capital x beta_a / (beta_a + beta_b)\n"
        "\n"
        "# Without beta data: V_a = V_b = total_capital / 2 (equal dollar split)"
    )
    pdf.body(
        "Optional stops: time stop (close after N days, default 3x half-life) and "
        "dollar stop (close if unrealised loss exceeds X% of capital, default 5%)."
    )

    pdf.h3("CLI Usage")
    pdf.code(
        "# Analyse a single pair with walk-forward validation\n"
        "python run.py pairs --pair GS/MS --period 5y --backtest --walk-forward 3\n"
        "\n"
        "# Scan a universe for cointegrated pairs\n"
        "python run.py pairs --scan --universe financials --period 2y\n"
        "\n"
        "# Scan with custom tickers\n"
        "python run.py pairs --scan --tickers GS,MS,JPM,BAC,C --period 2y"
    )

    pdf.h2("5.2  PCA Statistical Arbitrage")
    pdf.body(
        "Portfolio-level mean-reversion strategy. PCA decomposes returns into common "
        "factors (market, sector effects) and idiosyncratic residuals. The residuals "
        "are expected to mean-revert since they represent stock-specific mispricing "
        "uncorrelated with systematic market moves."
    )

    pdf.h3("Signal Generation (src/strategies/pca/signals.py)")
    pdf.body(
        "Computes rolling z-scores of cumulated PCA residuals (the Avellaneda-Lee "
        "s-score approach). A long position is taken in stocks with extreme negative "
        "z-scores (residual too low, expect recovery) and short in stocks with extreme "
        "positive z-scores."
    )
    pdf.code(
        "cumresid = residuals.cumsum()          # cumulated idiosyncratic return\n"
        "z = (cumresid - rolling_mean) / rolling_std\n"
        "\n"
        "Long:   z < -z_entry  (underperformed on idiosyncratic basis)\n"
        "Short:  z > +z_entry  (outperformed on idiosyncratic basis)\n"
        "Max simultaneous positions: top_n per side (default 3)"
    )

    pdf.h3("Universe Selection  -  Key Finding")
    pdf.body(
        "Walk-forward results across 6 universes (3 folds x 1 year each):"
    )
    pdf.param_table(
        ["Universe", "Fold 1", "Fold 2", "Fold 3", "Verdict"],
        [
            ["Energy", "+22.4%", "+11.4%", "+12.6%", "WORKS  -  oil price is a clean common factor"],
            ["Pharmacy", "-12.5%", "+22.9%", "-0.7%", "Inconsistent"],
            ["Financials", "-8.2%", "+4.3%", "-6.6%", "Losing OOS"],
            ["Staples", "-15.4%", "-2.0%", "-11.7%", "Losing OOS"],
            ["Tech", "-23.2%", "-7.5%", "-16.6%", "Losing OOS  -  stocks trend, don't mean-revert"],
            ["Airlines", "-6.0%", "-45.8%", "-14.9%", "Too idiosyncratic  -  events dominate"],
        ]
    )
    pdf.body(
        "Energy is the only universe with consistent OOS profitability. PCA works best "
        "when stocks share a single dominant common factor that explains most of the "
        "co-movement, leaving clean residuals."
    )

    pdf.h3("CLI Usage")
    pdf.code(
        "# Walk-forward validation on energy universe\n"
        "python run.py pca --universe energy --period 5y --walk-forward 3\n"
        "\n"
        "# Single in-sample backtest with test split\n"
        "python run.py pca --universe energy --period 3y --test-period 1y"
    )

    pdf.add_page()
    pdf.h2("5.3  Basket / ETF Arbitrage")
    pdf.body(
        "Trades the spread between an ETF and a weighted basket of its constituents. "
        "When the ETF trades at a discount to its fair value (implied by the weighted "
        "sum of constituent prices), the strategy buys the ETF and sells the basket. "
        "The ETF's arbitrage mechanism ensures this spread reverts."
    )

    pdf.h3("Spread Construction (src/analytics/basket.py)")
    pdf.body(
        "Uses rolling out-of-sample OLS to fit the basket weights. The spread is "
        "computed as the residual from regressing the ETF log-price on the constituent "
        "log-prices. Ridge regularisation can be applied to handle multicollinearity "
        "when constituents are highly correlated."
    )

    pdf.h3("EDGAR Integration (Survivorship Bias Correction)")
    pdf.body(
        "With --edgar-constituents --walk-forward, each fold uses the actual ETF "
        "constituents from SEC N-PORT filings at that point in time. Without this, "
        "using today's constituents for historical periods would bias results because "
        "you would be implicitly including knowledge of which stocks survived."
    )

    pdf.h3("CLI Usage")
    pdf.code(
        "# Multi-basket walk-forward with EDGAR survivorship correction\n"
        "python run.py basket-multi \\\n"
        "  --basket XLF:GS,MS,JPM,BAC,C \\\n"
        "  --basket XLK:MSFT,AAPL,NVDA \\\n"
        "  --walk-forward 5 --edgar-constituents\n"
        "\n"
        "# Simple single basket\n"
        "python run.py basket --etf XLF --stocks GS MS JPM --period 3y"
    )

    pdf.h2("5.4  CTA Trend Following")
    pdf.body(
        "Systematic trend following across 16 ETFs spanning equities, bonds, commodities, "
        "and FX. The strategy uses EWMAC signals to identify trending instruments and "
        "sizes positions proportionally to volatility targets. This is the best-performing "
        "and most thoroughly tested strategy in the project."
    )

    pdf.h3("Universe (src/strategies/cta/signals.py)")
    pdf.param_table(
        ["Asset Class", "Tickers", "Rationale"],
        [
            ["Equities", "SPY, QQQ, EFA, EEM, IWM", "US and international equity trends"],
            ["Bonds", "TLT, IEF, SHY, TIP", "Duration and inflation rate trends"],
            ["Commodities", "GLD, SLV, USO, DBA", "Gold, silver, oil, agricultural trends"],
            ["FX", "UUP, FXE, FXY", "Dollar, Euro, Yen trends"],
        ]
    )

    pdf.h3("Signal Generation")
    pdf.body(
        "Four EWMAC horizons are computed and averaged for each instrument. "
        "This multi-horizon approach captures trends at different time scales simultaneously."
    )
    pdf.param_table(
        ["Horizon", "Fast EMA", "Slow EMA", "Approx. Timeframe"],
        [
            ["Short", "8", "32", "~6 weeks"],
            ["Medium-short", "16", "64", "~3 months"],
            ["Medium", "32", "128", "~6 months"],
            ["Long", "64", "256", "~1 year"],
        ]
    )

    pdf.h3("Signal Modes")
    pdf.kv_table([
        ("binary (default)", "Collapses signal to {-1, 0, +1}. Full conviction on any non-zero signal. Simpler, more robust. Acts as a natural risk limiter in choppy markets."),
        ("continuous", "Scales signal to [-1, +1]: position = clip(signal/2, -1, 1). Preserves conviction magnitude. Better in theory but can stay partially invested when wrong."),
    ])

    pdf.h3("Regime Filter (--regime-filter)")
    pdf.body(
        "Suppresses long equity positions when SPY is below its 200-day moving average. "
        "The filter only applies to the 5 equity ETFs (SPY, QQQ, EFA, EEM, IWM). "
        "Short positions and non-equity instruments are unaffected  -  they often provide "
        "a natural hedge in bear markets."
    )

    pdf.h3("Parameter Sweep (src/strategies/cta/sweep.py)")
    pdf.body(
        "Grid search over threshold x vol_span x signal_mode across pre-computed "
        "walk-forward folds. Reports mean Sharpe for each combination. Key finding: "
        "vol_span=60 consistently outperforms the default 25 across all parameter combinations. "
        "The slower vol estimate prevents overreacting to short-term volatility spikes."
    )

    pdf.h3("Walk-Forward Results (vol_span=60, binary mode)")
    pdf.param_table(
        ["Fold", "Period", "Return", "Sharpe", "Notes"],
        [
            ["1", "May 2021 - May 2022", "+11.5%", "1.32", "Strong trend year"],
            ["2", "May 2022 - May 2023", "-6.4%", "-0.56", "Bonds and equities both sold off"],
            ["3", "May 2023 - May 2024", "+5.5%", "0.77", "Moderate trends"],
            ["4", "May 2024 - May 2025", "-0.7%", "-0.04", "Choppy, no clear trend"],
            ["5", "May 2025 - May 2026", "+20.6%", "2.44", "Strong trending environment"],
            ["Overall", "5 years", "+30.5%", "0.70", "Max DD: -15.3%"],
        ]
    )

    pdf.h3("CLI Usage")
    pdf.code(
        "# Recommended baseline\n"
        "python run.py cta --period 10y --walk-forward 5 --vol-span 60\n"
        "\n"
        "# With regime filter\n"
        "python run.py cta --period 10y --walk-forward 5 --vol-span 60 --regime-filter\n"
        "\n"
        "# Parameter sweep diagnostic (run first when tuning)\n"
        "python run.py cta --sweep --period 10y\n"
        "\n"
        "# Continuous signal mode with correlation adjustment\n"
        "python run.py cta --period 10y --walk-forward 5 --signal-mode continuous --corr-adjust"
    )

    # ?? Section 6: Backtesting ????????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Backtesting Engine")

    pdf.h2("Two Backtest Engines")
    pdf.body(
        "The project uses two different backtesting approaches depending on the strategy type:"
    )
    pdf.kv_table([
        ("src/backtest/engine.py", "Trade-log based. Used by pairs and basket strategies. Takes a list of completed trades with entry/exit prices and builds an equity curve by chaining P&L."),
        ("src/backtest/portfolio_engine.py", "Daily mark-to-market. Used by CTA, PCA, and the combined portfolio. Takes a positions/weights DataFrame and computes daily portfolio returns."),
    ])

    pdf.h2("src/backtest/portfolio_engine.py")
    pdf.h3("run_portfolio_backtest(positions_df, prices_df, capital, cost_bps, weights_df, cost_df)")
    pdf.body(
        "Computes a daily equity curve from positions and prices. The key mechanics:"
    )
    pdf.code(
        "# Weight computation (if weights_df not provided):\n"
        "n_active = positions_df.abs().sum(axis=1)\n"
        "weights = positions_df / n_active   # equal-weight among active positions\n"
        "\n"
        "# Return computation (weights lagged by 1 bar  -  no look-ahead):\n"
        "daily_ret = prices.pct_change()\n"
        "port_ret = (weights.shift(1) * daily_ret).sum(axis=1)\n"
        "\n"
        "# Cost computation:\n"
        "turnover = weights.diff().abs().sum(axis=1)\n"
        "cost = turnover * cost_bps / 10,000\n"
        "\n"
        "# Equity curve:\n"
        "net_ret = port_ret - cost\n"
        "equity = capital * (1 + net_ret).cumprod()"
    )
    pdf.body(
        "The weights.shift(1) is critical  -  it ensures that the weights computed at bar t "
        "are applied to returns starting at bar t+1. Without this, the backtest would "
        "have look-ahead bias."
    )

    pdf.h2("src/backtest/metrics.py  -  Performance Metrics")
    pdf.param_table(
        ["Metric", "Formula", "Interpretation"],
        [
            ["Total Return", "(final - start) / start", "Cumulative % gain over full period"],
            ["CAGR", "(final/start)^(252/n_days) - 1", "Annualised compound growth rate"],
            ["Sharpe Ratio", "mean(daily_ret) / std(daily_ret) x sqrt(252)", "Risk-adjusted return. >1 is good, >1.5 is strong"],
            ["Sortino Ratio", "mean(daily_ret) / std(negative_ret) x sqrt(252)", "Like Sharpe but only penalises downside volatility"],
            ["Max Drawdown", "min(equity / cummax(equity) - 1)", "Worst peak-to-trough decline. Most important risk metric"],
            ["Calmar Ratio", "CAGR / abs(max_drawdown)", "Return per unit of max drawdown pain"],
        ]
    )

    # ?? Section 7: Walk-Forward Validation ???????????????????????????????????
    pdf.add_page()
    pdf.h1("Walk-Forward Validation")

    pdf.h2("Why Walk-Forward?")
    pdf.body(
        "A standard in-sample backtest fits and tests on the same data. Even without "
        "explicit parameter optimisation, choices about indicators, thresholds, and "
        "universes implicitly reflect knowledge of the full history. Walk-forward "
        "validation tests the strategy on data it has never seen."
    )

    pdf.h2("How It Works")
    pdf.body(
        "With --walk-forward N, the available data is divided into N non-overlapping "
        "1-year test windows, rolling backwards from the most recent date. Signals are "
        "computed on the full history (causal  -  no look-ahead), but each fold's "
        "P&L is computed only on its 1-year test window."
    )
    pdf.code(
        "# Example: 5-fold walk-forward on 10 years of data\n"
        "Full history: 2016 ???????????????????????????????? 2026\n"
        "\n"
        "Fold 5: test on  2025 ??? 2026   (most recent)\n"
        "Fold 4: test on  2024 ??? 2025\n"
        "Fold 3: test on  2023 ??? 2024\n"
        "Fold 2: test on  2022 ??? 2023\n"
        "Fold 1: test on  2021 ??? 2022   (oldest)"
    )

    pdf.h2("Interpreting Results")
    pdf.body(
        "The stitched equity curve concatenates all fold equity curves end-to-end. "
        "This represents what the strategy would have earned in live trading over "
        "the test windows  -  a genuine OOS simulation."
    )
    pdf.bullet("Consistent positive Sharpe across folds = robust strategy")
    pdf.bullet("One or two negative folds is acceptable  -  markets are noisy")
    pdf.bullet("All folds negative or large drawdowns = strategy is curve-fit or broken")
    pdf.bullet("High variance between folds = regime-sensitive (needs regime filter)")

    # ?? Section 8: Risk Management ????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Risk Management")

    pdf.h2("Volatility Targeting")
    pdf.body(
        "The CTA strategy uses vol-targeting to size positions. Rather than betting "
        "a fixed fraction of capital on each instrument, each position is sized so "
        "that the expected contribution to portfolio volatility equals tau/N_active. "
        "This means high-vol instruments get smaller positions and low-vol instruments "
        "get larger positions  -  equalising risk contribution."
    )

    pdf.h2("Correlation Adjustment (--corr-adjust)")
    pdf.body(
        "The base vol-targeting formula divides equally by N_active, ignoring correlations. "
        "If 5 equity ETFs are all trending together, the formula over-allocates because "
        "it treats them as independent. The correlation adjustment multiplies the whole "
        "portfolio by tau / realized_portfolio_vol, pulling it back to the target "
        "regardless of correlation structure."
    )

    pdf.h2("Regime Filter (--regime-filter)")
    pdf.body(
        "The SPY 200-day MA regime filter suppresses long equity positions in bear markets. "
        "When SPY is below its 200-day MA, the strategy cannot go long on any of the 5 "
        "equity ETFs. Short positions and non-equity instruments are unaffected."
    )
    pdf.body(
        "Why this works: trend following in equities tends to be particularly bad during "
        "prolonged bear markets because prices fall in a jagged fashion with sharp "
        "rallies. The 200-day MA identifies sustained downtrends."
    )

    pdf.h2("Stop Losses (Pairs Strategy)")
    pdf.kv_table([
        ("Time stop", "Close trade if still open after N days (default: 3x half-life). Prevents getting stuck in a broken cointegration relationship."),
        ("Dollar stop", "Close if unrealised loss exceeds X% of capital (default: 5%). Hard risk limit per trade."),
        ("Z-score stop", "Close if |z| exceeds z_stop (default: 3.0). The spread diverged too far  -  cointegration may have broken."),
    ])

    pdf.h2("Transaction Costs")
    pdf.body(
        "Two cost models are available:"
    )
    pdf.kv_table([
        ("Fixed (default)", "Flat cost_bps applied to all turnover. Default 5 bps one-way. Simple and conservative."),
        ("Volume-adjusted", "Kyle's lambda model: cost = half_spread + 0.1 x vol x sqrt(order / ADV) x 10000. More realistic  -  liquid ETFs get 0.5-1.5 bps, illiquid stocks get 3-8 bps. Enable with --cost-model volume-adjusted."),
    ])

    # ?? Section 9: Paper Trading ??????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Paper Trading (Alpaca)")

    pdf.body(
        "The trade subcommand connects the CTA strategy's signal pipeline to Alpaca's "
        "paper trading API. It computes today's target positions, compares them to "
        "current paper holdings, and generates the rebalancing orders needed."
    )

    pdf.h2("Architecture")
    pdf.kv_table([
        ("src/trading/alpaca_trader.py", "Wrapper around alpaca-py TradingClient. Handles account info, position queries, order placement, and liquidation. Always uses paper=True."),
        ("src/trading/rebalancer.py", "Converts the last row of weights_df to a list of buy/sell orders. Skips orders below min_order_dollars to avoid tiny rebalances."),
        ("run.py _run_trade()", "Orchestrates the full pipeline: fetch prices, compute signals, compute weights, get current positions, compute orders, print table, optionally execute."),
    ])

    pdf.h2("API Key Setup")
    pdf.body("Two separate sets of credentials are required:")
    pdf.param_table(
        ["Env Variable", "Purpose", "Where to Get"],
        [
            ["ALPACA_API_KEY", "Live account key  -  for market data API", "alpaca.markets > Live Trading > API Keys"],
            ["ALPACA_SECRET_KEY", "Live account secret", "Same as above"],
            ["ALPACA_PAPER_KEY", "Paper trading key  -  for order execution", "alpaca.markets > Paper Trading > API Keys"],
            ["ALPACA_PAPER_SECRET", "Paper trading secret", "Same as above (copy at creation  -  shown only once)"],
        ]
    )
    pdf.body(
        "Important: Paper-only keys (PK...) do NOT have market data API access. "
        "You need live account keys for price fetching even when paper trading. "
        "Live keys + paper=True in TradingClient = live data, paper orders."
    )

    pdf.h2("Daily Workflow")
    pdf.code(
        "# 1. Set environment variables (once per terminal session)\n"
        "$env:ALPACA_API_KEY    = 'your_live_key'\n"
        "$env:ALPACA_SECRET_KEY = 'your_live_secret'\n"
        "$env:ALPACA_PAPER_KEY    = 'your_paper_key'\n"
        "$env:ALPACA_PAPER_SECRET = 'your_paper_secret'\n"
        "\n"
        "# 2. Preview today's orders (safe  -  no orders placed)\n"
        "python run.py trade\n"
        "\n"
        "# 3. Execute orders (places real paper trades)\n"
        "python run.py trade --execute\n"
        "\n"
        "# 4. Close all positions (e.g. before a holiday)\n"
        "python run.py trade --liquidate"
    )

    pdf.h2("How Positions Are Sized")
    pdf.body(
        "The trade command uses the same vol-targeting formula as the backtest. "
        "The last row of weights_df represents today's signal:"
    )
    pdf.code(
        "# For each instrument:\n"
        "target_notional = weight x capital\n"
        "current_notional = current_market_value (from Alpaca positions)\n"
        "order_notional = target_notional - current_notional\n"
        "\n"
        "# Skip if |order_notional| < min_order_dollars (default $50)\n"
        "# BUY if order_notional > 0\n"
        "# SELL if order_notional < 0"
    )
    pdf.body(
        "Orders are placed as dollar-notional DAY market orders. Alpaca supports "
        "fractional shares for most ETFs, so exact dollar amounts are achievable. "
        "Orders expire at end of day if not filled."
    )

    pdf.h2("Important Limitations")
    pdf.bullet("Signals are based on closing prices from the previous day. The system should be run before market open to place orders that execute at open prices.")
    pdf.bullet("No intraday monitoring  -  once orders are placed, they run until filled or expired.")
    pdf.bullet("Short positions require a margin account. The default paper account may not support shorting all ETFs.")
    pdf.bullet("The system does not handle partial fills  -  if an order partially fills, the next run will attempt to complete the rebalance.")

    # ?? Section 10: Combined Portfolio ????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Combined Portfolio")

    pdf.body(
        "The portfolio subcommand runs all four strategies in headless mode, "
        "combines their daily P&L with equal-risk weighting, and shows a unified "
        "performance view."
    )

    pdf.h2("Equal-Risk Weighting")
    pdf.body(
        "Each strategy is weighted by inverse volatility, rebalanced monthly. "
        "This gives lower-vol strategies more capital so each contributes equally "
        "to portfolio risk."
    )
    pdf.code(
        "# Monthly rebalancing:\n"
        "vol_i = rolling(63 days).std(daily_pnl_i) x sqrt(252)\n"
        "raw_weight_i = 1 / vol_i\n"
        "weight_i = raw_weight_i / sum(raw_weights)  # normalise to sum to 1"
    )

    pdf.h2("CLI Usage")
    pdf.code(
        "python run.py portfolio --period 5y\n"
        "python run.py portfolio --period 5y --exclude pca  # if PCA isn't working\n"
        "python run.py portfolio --period 5y --capital 100000"
    )

    # ?? Section 11: CLI Reference ?????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("CLI Reference")

    pdf.body("All commands are run from the project root: python run.py <subcommand> [options]")

    pdf.h2("pairs")
    pdf.param_table(
        ["Flag", "Default", "Description"],
        [
            ["--pair A/B", "required", "Single pair to analyse, e.g. GS/MS"],
            ["--period", "2y", "Data lookback period"],
            ["--backtest", "off", "Run backtest and show equity curve"],
            ["--walk-forward N", "off", "N non-overlapping 1-year OOS folds"],
            ["--kalman-delta", "1e-4", "Kalman filter noise. Higher = faster adaptation"],
            ["--test-period", "None", "Hold-out period for OOS test (3mo/6mo/1y/2y)"],
            ["--z-entry", "2.0", "Entry threshold for z-score"],
            ["--z-exit", "0.5", "Exit threshold"],
            ["--z-stop", "3.0", "Stop-loss threshold"],
            ["--max-hold-days", "auto", "Time stop in days (default: 3x half-life)"],
            ["--dollar-stop", "5.0", "Dollar stop as % of capital"],
            ["--scan", "off", "Scan universe for cointegrated pairs"],
            ["--universe", "configured", "Named universe for --scan"],
        ]
    )

    pdf.h2("pca")
    pdf.param_table(
        ["Flag", "Default", "Description"],
        [
            ["--universe NAME", "required", "Named universe: financials/energy/tech/staples/airlines/pharmacy"],
            ["--period", "2y", "Data lookback period"],
            ["--walk-forward N", "off", "N non-overlapping 1-year OOS folds"],
            ["--window", "60", "Rolling window for PCA and z-scoring (days)"],
            ["--n-factors", "3", "Number of PCA factors to extract"],
            ["--top-n", "3", "Max simultaneous positions per side"],
            ["--z-entry", "2.0", "Entry threshold"],
            ["--z-exit", "0.5", "Exit threshold"],
            ["--z-stop", "3.0", "Stop-loss threshold"],
            ["--test-period", "None", "Hold-out period for OOS test"],
            ["--cost-bps", "5.0", "Transaction cost in bps"],
        ]
    )

    pdf.h2("cta")
    pdf.param_table(
        ["Flag", "Default", "Description"],
        [
            ["--period", "5y", "Data lookback period"],
            ["--walk-forward N", "off", "N non-overlapping 1-year OOS folds"],
            ["--sweep", "off", "Grid search over threshold x vol_span x signal_mode"],
            ["--vol-span N", "25", "EWM span for vol estimation. 60 recommended."],
            ["--vol-target", "0.20", "Annualised portfolio vol target (tau)"],
            ["--signal-mode", "binary", "binary={-1,0,+1} or continuous=scaled"],
            ["--threshold", "0.0", "Signal flat-band  -  must exceed to enter"],
            ["--corr-adjust", "off", "Scale weights by realized portfolio vol"],
            ["--regime-filter", "off", "Suppress equity longs when SPY < 200-day MA"],
            ["--weight-cap", "0", "Per-instrument weight cap (0=none)"],
            ["--cost-bps", "5.0", "Transaction cost in bps"],
            ["--cost-model", "fixed", "fixed or volume-adjusted (Kyle's lambda)"],
            ["--data-provider", "yfinance", "yfinance or alpaca"],
            ["--capital", "20000", "Starting capital in dollars"],
        ]
    )

    pdf.h2("trade")
    pdf.param_table(
        ["Flag", "Default", "Description"],
        [
            ["--capital", "0 (=account equity)", "Override capital amount"],
            ["--vol-span N", "60", "EWM span for vol estimation"],
            ["--regime-filter", "off", "Apply SPY 200-day MA filter"],
            ["--min-order", "50", "Minimum order size in dollars"],
            ["--execute", "off", "Place orders (default: dry-run preview)"],
            ["--liquidate", "off", "Close all positions and exit"],
        ]
    )

    pdf.h2("portfolio")
    pdf.param_table(
        ["Flag", "Default", "Description"],
        [
            ["--period", "5y", "Data lookback period"],
            ["--capital", "100000", "Total capital across all strategies"],
            ["--cost-bps", "5.0", "Transaction cost in bps"],
            ["--exclude", "None", "Strategies to exclude: cta/pca/basket"],
        ]
    )

    # ?? Section 12: Testing ???????????????????????????????????????????????????
    pdf.add_page()
    pdf.h1("Testing")

    pdf.body(
        "The test suite uses pytest and covers core analytics and backtest engine behaviour. "
        "Tests use synthetic price data (no external API calls) so they run instantly."
    )

    pdf.h2("Running Tests")
    pdf.code("pytest tests/ -v")

    pdf.h2("Test Fixtures (tests/conftest.py)")
    pdf.kv_table([
        ("prices_df", "16 instruments, 600 bars, log-normal with upward drift. Seed=42 for reproducibility. Used for CTA and portfolio engine tests."),
        ("small_prices_df", "4 instruments, 300 bars, seed=7. Faster for unit tests with fewer instruments."),
    ])

    pdf.h2("Test Coverage")
    pdf.param_table(
        ["File", "Tests", "What is Verified"],
        [
            ["test_cta_signals.py", "6", "Binary values in {-1,0,+1}, threshold zeroing, continuous range [-1,+1], output shape, threshold reduces positions, continuous has more granularity"],
            ["test_portfolio_engine.py", "6", "Buy-and-hold grows equity, flat positions stay flat, costs reduce equity, metrics dict shape, positive return = positive Sharpe, custom weights_df used"],
            ["test_analytics_cta.py", "6", "EWMAC clipped to [-2,2], vol non-negative, zero positions = zero weights, weight shape, weight cap respected, corr_adjust non-zero after warmup"],
        ]
    )

    pdf.h2("Adding New Tests")
    pdf.body(
        "Add new test files to tests/. Use the fixtures from conftest.py. "
        "Tests should not call fetch_price() or any function that makes network requests. "
        "For integration tests that need real data, use a separate test marker."
    )

    # ?? Section 13: Extending the Project ????????????????????????????????????
    pdf.add_page()
    pdf.h1("Extending the Project")

    pdf.h2("Adding a New Strategy")
    pdf.body("Follow this pattern:")
    pdf.bullet("Create src/strategies/my_strategy/ with signals.py, backtest.py, viz.py")
    pdf.bullet("Add analytics functions to src/analytics/my_strategy.py (pure functions)")
    pdf.bullet("Add _run_my_strategy() and _register_my_strategy() to run.py")
    pdf.bullet("Register in main() with _register_my_strategy(subparsers)")
    pdf.bullet("Add smoke tests to tests/test_my_strategy.py")

    pdf.h2("Adding a New Universe")
    pdf.body("Add tickers to SCAN_UNIVERSES in src/strategies/pairs/config.py. The PCA and scan subcommands will pick it up automatically.")

    pdf.h2("Changing the Data Provider")
    pdf.body(
        "fetch_prices_bulk() and fetch_ohlcv_bulk() accept provider='yfinance' or "
        "provider='alpaca'. To add a new provider, add a new fetcher in src/data/ "
        "that returns the same dict[ticker, Series] format, then add a branch in "
        "fetch_prices_bulk() in fetcher.py."
    )

    pdf.h2("Regenerating This Document")
    pdf.body("After making changes to the code, regenerate the PDF with:")
    pdf.code("python generate_docs.py")
    pdf.body("The output is written to docs/Quant_Project_Guide.pdf.")

    pdf.h2("Suggested Next Steps")
    pdf.param_table(
        ["Feature", "Difficulty", "Description"],
        [
            ["Scheduled daily runner", "Easy", "Script that runs 'python run.py trade --execute' each morning before market open"],
            ["Regime filter sweep", "Easy", "Add regime_filter to sweep_cta_params() grid to quantify its impact"],
            ["PCA walk-forward (more universes)", "Easy", "Test pharmacy and financials with wider z_entry (try 2.5, 3.0)"],
            ["Pairs walk-forward (more pairs)", "Medium", "Run walk-forward on all 11 configured pairs, rank by OOS Sharpe"],
            ["Live trading (real money)", "Hard", "Change TradingClient(paper=False), add position limits, circuit breakers"],
            ["Risk parity portfolio", "Medium", "Replace inverse-vol weighting with full covariance-based risk parity"],
            ["Factor exposure analysis", "Medium", "Regress strategy returns on Fama-French factors (market, value, momentum)"],
        ]
    )


# ???????????????????????????????????????????????????????????????????????????????
# Run
# ???????????????????????????????????????????????????????????????????????????????
if __name__ == "__main__":
    pdf = Doc()
    build(pdf)
    pdf.output(str(OUT_PATH))
    print(f"Written: {OUT_PATH}  ({OUT_PATH.stat().st_size // 1024} KB)")

"""
Generates the session summary PDF.
Run from the project root: python docs/generate_session_summary.py
"""

from fpdf import FPDF
from datetime import date
from pathlib import Path

OUTPUT = Path(__file__).parent / f"session_summary_{date.today()}.pdf"


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "Quant Project - Session Summary", align="R")
        self.ln(2)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(160, 160, 160)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def h1(self, text):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(26, 37, 47)   # _HEADER_BG dark navy
        self.ln(2)
        self.cell(0, 10, text)
        self.ln(12)

    def h2(self, text):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(44, 62, 80)   # _SECTION_BG
        self.set_fill_color(244, 246, 248)
        self.cell(0, 8, f"  {text}", fill=True)
        self.ln(10)

    def h3(self, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(44, 62, 80)
        self.ln(1)
        self.cell(0, 6, text)
        self.ln(7)

    def body(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 5.5, text)
        self.ln(3)

    def bullet(self, text, indent=6):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.set_x(self.l_margin + indent)
        self.cell(4, 5.5, chr(149))   # bullet dot
        self.multi_cell(0, 5.5, text)

    def code(self, text):
        self.set_font("Courier", "", 9)
        self.set_text_color(40, 40, 40)
        self.set_fill_color(248, 248, 248)
        self.set_x(self.l_margin + 6)
        self.multi_cell(0, 5, f"  {text}", fill=True)
        self.ln(1)

    def rule(self):
        self.set_draw_color(220, 220, 220)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)


pdf = PDF()
pdf.set_margins(18, 18, 18)
pdf.set_auto_page_break(auto=True, margin=18)
pdf.add_page()

# ── Title block ───────────────────────────────────────────────────────────────
pdf.set_font("Helvetica", "B", 22)
pdf.set_text_color(26, 37, 47)
pdf.cell(0, 12, "Quant Project", align="C")
pdf.ln(10)
pdf.set_font("Helvetica", "", 13)
pdf.set_text_color(80, 80, 80)
pdf.cell(0, 7, "Session Summary", align="C")
pdf.ln(6)
pdf.set_font("Helvetica", "", 10)
pdf.set_text_color(130, 130, 130)
pdf.cell(0, 6, f"Date: {date.today().strftime('%B %d, %Y')}", align="C")
pdf.ln(12)
pdf.rule()

# ── 1. What Was Built ─────────────────────────────────────────────────────────
pdf.h2("1. What Was Built This Session")

pdf.h3("Multi-Strategy Architecture Restructure")
pdf.body(
    "The project was reorganised from a flat single-strategy layout into a scalable "
    "multi-strategy architecture. Every future strategy now has a clearly defined home."
)
pdf.bullet("src/strategies/pairs/  -all pairs-trading logic (spread, signals, config, viz, backtest)")
pdf.bullet("src/analytics/         -shared statistical tools (ADF test, half-life)")
pdf.bullet("src/backtest/          -strategy-agnostic backtest engine and metrics")
pdf.bullet("src/viz/theme.py       -shared color palette imported by all strategy charts")
pdf.bullet("notebooks/pairs/       -notebooks moved into a strategy subfolder")
pdf.ln(2)
pdf.body("Adding a future strategy (momentum, mean reversion, options) now requires exactly two things: a new src/strategies/<name>/ folder and one registration function in run.py.")

pdf.h3("Data Layer Upgrade")
pdf.body(
    "The data fetcher previously cached only closing prices. It now fetches and caches full "
    "OHLCV data (Open, High, Low, Close, Volume) for every ticker. Old single-column cache "
    "files are automatically refreshed on next use."
)
pdf.bullet("fetch_ohlcv(ticker, period)         -single ticker, returns 5-column DataFrame")
pdf.bullet("fetch_pair_ohlcv(ticker_a, ticker_b) -aligned OHLCV for both legs of a pair")
pdf.bullet("fetch_price / fetch_pair            -unchanged signatures; backward compatible")
pdf.ln(2)

pdf.h3("Backtest Engine")
pdf.body(
    "A full vectorised backtest engine was built. Given a signal DataFrame from the pairs "
    "pipeline, it simulates every trade, builds an equity curve, and computes performance statistics."
)
pdf.bullet("src/backtest/engine.py   -run_backtest(): trade log -> daily equity curve")
pdf.bullet("src/backtest/metrics.py  -compute_metrics(): equity curve -> performance dict")
pdf.bullet("src/strategies/pairs/backtest.py -build_trade_log() with hedge-ratio-adjusted sizing")
pdf.ln(2)
pdf.body("Position sizing is dollar-neutral and hedge-ratio adjusted per leg ($10,000 default). P&L uses close-to-close fills, a known simplification suitable for daily bars at this stage.")

pdf.h3("New Output Windows (--backtest flag)")
pdf.body("Running with --backtest adds four new browser windows to the existing three:")
pdf.bullet("Equity Curve       -two-panel: portfolio value + drawdown, shaded trade bands")
pdf.bullet("Trade P&L          -bar chart of per-trade returns (green = win, red = loss)")
pdf.bullet("Backtest Metrics   -styled table: returns, Sharpe, drawdown, win rate, profit factor")
pdf.bullet("Backtest Explanation -contextual plain-English interpretation of every metric")
pdf.ln(2)

pdf.h3("Named Browser Tabs")
pdf.body(
    "All browser windows now open with descriptive tab titles instead of numbers. "
    "The _show(fig, title) helper in run.py injects a <title> tag into each HTML export."
)
pdf.bullet("Examples: 'KO/PEP -Stats', 'KO/PEP -Charts', 'KO/PEP -Backtest Explanation'")
pdf.ln(3)

# ── 2. How to Run ─────────────────────────────────────────────────────────────
pdf.h2("2. How to Run")

pdf.h3("Signal analysis only (3 windows)")
pdf.code("python run.py pairs --pair KO/PEP")

pdf.h3("Signal analysis + backtest (7 windows)")
pdf.code("python run.py pairs --pair KO/PEP --backtest")

pdf.h3("Scan all configured pairs")
pdf.code("python run.py pairs --all")

pdf.h3("Custom parameters")
pdf.code("python run.py pairs --pair JPM/BAC --period 1y --window 30 --z-entry 1.8 --backtest")

pdf.h3("Help")
pdf.code("python run.py --help")
pdf.code("python run.py pairs --help")
pdf.ln(3)

# ── 3. Current Project Structure ─────────────────────────────────────────────
pdf.add_page()
pdf.h2("3. Current Project Structure")

structure = [
    ("run.py",                                  "CLI entry point -subcommand-based"),
    ("requirements.txt",                         "Python dependencies"),
    ("data/cache/",                              "Auto-populated OHLCV CSV cache"),
    ("docs/",                                    "Session summaries and documentation"),
    ("notebooks/pairs/01_pairs_trading.ipynb",  "Deep-dive: cointegration, spread, signals"),
    ("notebooks/pairs/02_scenarios.ipynb",      "Sandbox: parameter tuning, custom pairs"),
    ("src/data/fetcher.py",                      "yfinance wrapper -fetch_ohlcv, fetch_pair_ohlcv"),
    ("src/analytics/stationarity.py",            "adf_test, compute_half_life (shared)"),
    ("src/backtest/engine.py",                   "run_backtest() -trade log to equity curve"),
    ("src/backtest/metrics.py",                  "compute_metrics() -performance statistics"),
    ("src/viz/theme.py",                         "Shared color palette constants"),
    ("src/strategies/base.py",                   "Abstract BaseStrategy interface"),
    ("src/strategies/pairs/config.py",           "PAIRS list and DEFAULT_PARAMS"),
    ("src/strategies/pairs/spread.py",           "compute_hedge_ratio, compute_spread"),
    ("src/strategies/pairs/signals.py",          "compute_zscore, generate_signals"),
    ("src/strategies/pairs/backtest.py",         "build_trade_log, run_pairs_backtest"),
    ("src/strategies/pairs/viz.py",              "All Plotly chart functions (10 total)"),
]

pdf.set_font("Courier", "B", 9)
pdf.set_text_color(44, 62, 80)
pdf.set_fill_color(230, 236, 242)
pdf.cell(75, 7, "  File", fill=True)
pdf.cell(0, 7, "  Purpose", fill=True)
pdf.ln(7)

for i, (path, desc) in enumerate(structure):
    bg = (248, 250, 252) if i % 2 == 0 else (255, 255, 255)
    pdf.set_fill_color(*bg)
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(75, 6, f"  {path}", fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"  {desc}", fill=True)
    pdf.ln(6)

pdf.ln(5)

# ── 4. Key Concepts Covered ───────────────────────────────────────────────────
pdf.h2("4. Key Concepts Covered")

concepts = [
    ("Cointegration",      "Two non-stationary series whose linear combination is stationary. The statistical foundation of pairs trading."),
    ("OLS Hedge Ratio (b)","Estimated by regressing log(A) on log(B). Makes the spread as stationary as possible. Drives position sizing."),
    ("ADF Test",           "Augmented Dickey-Fuller test. p < 0.05 means the spread is stationary -the core assumption is validated."),
    ("Half-Life",          "From AR(1) fit: how many days for the spread to revert halfway to its mean. Guides rolling window and holding period."),
    ("Rolling Z-Score",    "z = (spread - rolling_mean) / rolling_std. Expresses divergence in standard deviations for threshold-based signals."),
    ("State Machine",      "Signal generator that tracks position state to prevent overlapping trades. Entry / hold / exit or stop."),
    ("Vectorised Backtest","Compute all signals first, then replay trades in a single forward pass. Simpler than event-based; fine for daily bars."),
    ("Sharpe Ratio",       "mean(daily returns) / std(daily returns) * sqrt(252). Risk-adjusted return. > 1.0 is good; negative means losing on risk basis."),
    ("Profit Factor",      "Sum of winning P&L / sum of losing P&L. > 1.0 required for profitability. > 1.5 is the professional target."),
    ("Max Drawdown",       "Worst peak-to-trough equity decline. Measures the worst-case experience of holding the strategy."),
]

for term, explanation in concepts:
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(48, 6, term)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 6, explanation)
    pdf.ln(1)

pdf.ln(3)

# ── 5. Key Finding: Current Pairs ─────────────────────────────────────────────
pdf.h2("5. Key Finding: Current Configured Pairs")

pdf.body(
    "None of the four currently configured pairs (KO/PEP, JPM/BAC, XOM/CVX, MSFT/GOOGL) "
    "passed the ADF stationarity test over the 2-year lookback window. This is a real market "
    "finding, not a code bug -the pairs have diverged structurally in recent years."
)
pdf.body(
    "KO went +32% while PEP fell -10% over the same period (opposite directions), producing "
    "a hedge ratio near zero and a non-stationary spread. Before running a live backtest, "
    "finding genuinely cointegrated pairs is the most important next step."
)
pdf.ln(3)

# ── 6. Future Recommendations ─────────────────────────────────────────────────
pdf.add_page()
pdf.h2("6. Future Recommendations")

pdf.h3("Immediate Priority: Find Valid Pairs")
pdf.body(
    "The current pairs fail the stationarity test. Before improving the backtest engine further, "
    "find pairs that actually cointegrate. Good candidates to test:"
)
pdf.bullet("GS / MS  (Goldman Sachs vs Morgan Stanley -investment banking peers)")
pdf.bullet("DAL / UAL  (Delta vs United -same routes, same fuel costs)")
pdf.bullet("CVS / WBA  (pharmacy retail duopoly)")
pdf.bullet("Try shorter periods (--period 1y or 6mo) on existing pairs -a shorter window may reveal a valid regime")
pdf.ln(2)

pdf.h3("Automated Pair Discovery")
pdf.body(
    "Instead of hand-picking pairs, scan a universe of stocks for cointegrated candidates. "
    "This is the next major analytical feature:"
)
pdf.bullet("Build src/analytics/cointegration.py -Johansen test (tests multiple series simultaneously)")
pdf.bullet("Add a scan command: python run.py pairs --scan-universe SP500 --sector Financials")
pdf.bullet("Filter by: ADF p-value, half-life range, beta range, minimum trade count")
pdf.ln(2)

pdf.h3("Rolling Hedge Ratio")
pdf.body(
    "Currently beta is estimated using the full lookback window -an in-sample simplification "
    "that introduces look-ahead bias. A rolling beta re-estimates it using only past data:"
)
pdf.bullet("Add compute_rolling_hedge_ratio(series_a, series_b, window) to spread.py")
pdf.bullet("Typical window: 252 days (1 year). Recalculate daily or weekly")
pdf.bullet("This is a prerequisite for a truly out-of-sample backtest")
pdf.ln(2)

pdf.h3("Walk-Forward Validation")
pdf.body(
    "The current backtest trains and tests on the same data window -a form of in-sample testing. "
    "Walk-forward validation splits the data into sequential train/test folds:"
)
pdf.bullet("Train on first N months (estimate beta, confirm stationarity)")
pdf.bullet("Test on the following M months (run signals and backtest on unseen data)")
pdf.bullet("Roll forward and repeat. Average performance across all test windows")
pdf.bullet("This is the gold standard for validating a systematic strategy before trading")
pdf.ln(2)

pdf.h3("Transaction Costs and Slippage")
pdf.body(
    "The current backtest assumes zero friction. In reality, even with zero-commission brokers, "
    "slippage (the difference between the signal price and the fill price) eats into P&L:"
)
pdf.bullet("Add slippage_bps parameter to run_pairs_backtest() -e.g., 5 bps round-trip")
pdf.bullet("Adjust entry/exit prices: entry_price * (1 + slippage) for buys, * (1 - slippage) for sells")
pdf.bullet("At 5 bps on $20,000 capital that's ~$10 per round-trip -meaningful on short-hold trades")
pdf.ln(2)

pdf.h3("Position Sizing")
pdf.body(
    "Current sizing is fixed at $10,000 per leg regardless of signal strength. Better approaches:"
)
pdf.bullet("Size by z-score magnitude: larger position when z-score is more extreme")
pdf.bullet("Size by volatility: reduce size when the spread is unusually volatile (VaR-based)")
pdf.bullet("Kelly criterion: size based on estimated edge and variance -academic but powerful")
pdf.ln(2)

pdf.h3("Alpaca Integration (Paper Trading)")
pdf.body(
    "When ready to move beyond backtesting, Alpaca (alpaca.markets) is the recommended next "
    "data and execution layer. It offers:"
)
pdf.bullet("Free paper trading account -simulate real orders with real market data")
pdf.bullet("Historical OHLCV data API (replaces yfinance -more reliable, official)")
pdf.bullet("Same Python SDK (alpaca-py) for paper and live trading -minimal code change")
pdf.bullet("The fetcher.py abstraction is already designed for this swap")
pdf.ln(2)
pdf.body("Migration path: add AlpacaProvider class that implements the same fetch_ohlcv() interface. Switch by changing one import.")

pdf.h3("Additional Strategies")
pdf.body(
    "The multi-strategy architecture is ready. Next strategies to consider adding "
    "(in rough order of complexity):"
)
pdf.bullet("Momentum -buy stocks making new highs, short those making new lows (trend following)")
pdf.bullet("Mean Reversion (single name) -Bollinger Band entries on individual stocks")
pdf.bullet("ETF Arbitrage -pairs between an ETF and a basket of its components")
pdf.bullet("Sector rotation -rank sectors by relative momentum, rotate monthly")
pdf.ln(2)

pdf.h3("Notebook Updates")
pdf.body(
    "The notebooks haven't been updated to reflect the backtest engine yet. "
    "Next notebook additions:"
)
pdf.bullet("03_backtest.ipynb -walkthrough of the backtest mechanics, equity curve interpretation")
pdf.bullet("Update 01_pairs_trading.ipynb -add a section on why the current pairs are failing the ADF test")
pdf.bullet("Update 02_scenarios.ipynb -add scenario comparison for different backtest periods")
pdf.ln(3)

# ── Footer block ──────────────────────────────────────────────────────────────
pdf.rule()
pdf.set_font("Helvetica", "I", 9)
pdf.set_text_color(150, 150, 150)
pdf.cell(0, 6, f"Generated {date.today().strftime('%B %d, %Y')}  - Quant Project  - docs/session_summary_{date.today()}.pdf", align="C")

pdf.output(str(OUTPUT))
print(f"Saved: {OUTPUT}")

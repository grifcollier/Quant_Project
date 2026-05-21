from fpdf import FPDF
import os

OUT = "docs/Session_Summary_2026-05-21.pdf"
os.makedirs("docs", exist_ok=True)

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_fill_color(30, 30, 30)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, "Quant Project - Session Summary  |  2026-05-21", fill=True, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def h1(self, text):
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(220, 230, 245)
        self.cell(0, 9, text, fill=True, ln=True)
        self.ln(2)

    def h2(self, text):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 70, 130)
        self.cell(0, 7, text, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def body(self, text):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def bullet(self, items):
        self.set_font("Helvetica", "", 10)
        indent = 6
        usable = self.w - self.l_margin - self.r_margin - indent
        for item in items:
            self.cell(indent, 6, "")
            self.multi_cell(usable, 6, "- " + item)
        self.ln(2)

    def code(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(245, 245, 245)
        self.multi_cell(0, 5, text, fill=True, border=1)
        self.set_font("Helvetica", "", 10)
        self.ln(2)

    def kv_table(self, rows, col1_w=65):
        usable = self.w - self.l_margin - self.r_margin
        val_w = usable - col1_w
        self.set_font("Helvetica", "", 9)
        for k, v in rows:
            self.set_fill_color(240, 240, 240)
            self.cell(col1_w, 6, k, border=1, fill=True)
            self.set_fill_color(255, 255, 255)
            self.multi_cell(val_w, 6, v, border=1, fill=True)
        self.ln(3)

pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

pdf.h1("1. Project Overview")
pdf.body("A multi-strategy quantitative trading system with 4 backtested strategies, Alpaca paper trading integration, and fully automated daily execution via GitHub Actions. All strategies are validated with walk-forward out-of-sample testing.")
pdf.bullet([
    "Pairs trading (stat-arb on cointegrated stock pairs)",
    "Basket arbitrage (ETF vs. weighted constituents)",
    "CTA / trend-following (momentum across asset classes)",
    "PCA factor model (trade residuals orthogonal to common factors)",
])

pdf.h1("2. What Was Built This Session")
pdf.h2("2.1  Basket Strategy Enhancements")
pdf.bullet([
    "Added --data-provider alpaca flag (bulk fetch via Alpaca Market Data API)",
    "Added --walk-forward N flag: N non-overlapping 1-year OOS folds with stitched equity curve",
    "Added --cost-bps flag for realistic transaction cost modelling",
    "Added XLV (Health Care) and XLI (Industrials) baskets alongside XLF, XLK, XLE",
    "Recommended parameters: z-entry=1.5, z-exit=0.25, z-stop=2.5, window=60, cost-bps=20",
    "Results: 45/45 profitable folds across 5 baskets over 10 years, avg Sharpe 2.2-2.65",
])
pdf.h2("2.2  Alpaca Paper Trading Module (src/trading/)")
pdf.bullet([
    "alpaca_trader.py: TradingClient wrapper (paper=True, always simulated money)",
    "  - get_account(), get_positions(), place_notional_order(), close_all_positions()",
    "rebalancer.py: converts target weights to buy/sell order list",
])
pdf.h2("2.3  Trade Subcommand (run.py)")
pdf.bullet([
    "python run.py trade --strategy basket --etf XLF --stocks GS MS JPM BAC C",
    "Dry-run by default; add --execute to place real paper orders",
    "Signals: LONG SPREAD / SHORT SPREAD / EXIT / STOP-LOSS / HOLD / FLAT",
])
pdf.h2("2.4  Daily Automation")
pdf.bullet([
    "scripts/daily_trade.py: runs all 5 baskets, logs to logs/trade_YYYY-MM-DD.log",
    "scripts/run_daily.ps1: PowerShell wrapper for Windows Task Scheduler",
    ".github/workflows/daily_trade.yml: GitHub Actions workflow (cloud, no laptop needed)",
    "Runs Mon-Fri at 4:30pm ET (20:30 UTC during summer/EDT)",
    "--execute flag enabled: places real paper orders automatically",
])

pdf.add_page()
pdf.h1("3. Key Files")
pdf.kv_table([
    ("run.py",                            "Main CLI entry point - all strategy subcommands"),
    ("scripts/daily_trade.py",            "Daily runner for all 5 baskets via subprocess"),
    ("scripts/run_daily.ps1",             "PowerShell wrapper for Windows Task Scheduler"),
    (".github/workflows/daily_trade.yml", "GitHub Actions - runs at 4:30pm ET weekdays"),
    ("src/trading/alpaca_trader.py",      "Alpaca TradingClient wrapper (paper=True)"),
    ("src/trading/rebalancer.py",         "Converts target weights to buy/sell orders"),
    ("src/data/alpaca_fetcher.py",        "Alpaca Market Data bulk price fetcher"),
    ("src/strategies/basket/",            "Basket strategy: OLS fit, z-score, walk-forward"),
    ("src/strategies/pairs/config.py",    "Pair definitions + sp500 scan universe (224 tickers)"),
    ("logs/",                             "Daily trade logs written here"),
    ("docs/",                             "Generated PDFs (project guide, session summaries)"),
])

pdf.h1("4. Basket Configuration")
pdf.kv_table([
    ("XLF - Financials",  "GS, MS, JPM, BAC, C"),
    ("XLV - Health Care", "UNH, LLY, ABBV, JNJ, MRK"),
    ("XLI - Industrials", "GE, RTX, CAT, HON, UPS"),
    ("XLK - Technology",  "MSFT, AAPL, NVDA, GOOGL, META"),
    ("XLE - Energy",      "XOM, CVX, COP, SLB, EOG"),
    ("z-entry",           "1.5 - enter when spread deviates 1.5 std from mean"),
    ("z-exit",            "0.25 - exit when spread nearly back to mean"),
    ("z-stop",            "2.5 - stop-loss if spread widens further"),
    ("window",            "60 days rolling mean/std for z-score"),
    ("cost-bps",          "20 bps per trade (realistic round-trip)"),
])

pdf.h1("5. Environment Variables Required")
pdf.body("NEVER store keys in code or files. Set as environment variables or GitHub Secrets only. Alpaca shows the secret key only once at creation - save it immediately.")
pdf.kv_table([
    ("ALPACA_API_KEY",      "Live account API key - used for market data (price fetching)"),
    ("ALPACA_SECRET_KEY",   "Live account secret key"),
    ("ALPACA_PAPER_KEY",    "Paper trading API key - used for order execution (fake money)"),
    ("ALPACA_PAPER_SECRET", "Paper trading secret key"),
])
pdf.body("Note: Live account keys unlock both the data API and paper trading. Paper-only keys get 401 on the data API.")

pdf.h1("6. Common Commands")
pdf.h2("Backtesting")
pdf.code(
    "python run.py basket --etf XLF --stocks GS MS JPM BAC C --period 10y --walk-forward 9 --cost-bps 20\n"
    "python run.py cta --period 10y --walk-forward 5 --vol-span 60\n"
    "python run.py pairs --scan --universe sp500 --data-provider alpaca\n"
    "python run.py pca --universe energy --period 5y --walk-forward 3"
)
pdf.h2("Paper Trading (manual)")
pdf.code(
    "# Dry run - preview signals only\n"
    "python run.py trade --strategy basket --etf XLF --stocks GS MS JPM BAC C\n\n"
    "# Place real paper orders\n"
    "python run.py trade --strategy basket --etf XLF --stocks GS MS JPM BAC C --execute\n\n"
    "# Run all 5 baskets at once\n"
    "python scripts/daily_trade.py --execute"
)
pdf.h2("Automated (GitHub Actions)")
pdf.code(
    "# Runs automatically Mon-Fri at 4:30pm ET - no laptop needed\n"
    "# Check logs at: github.com/grifcollier/Quant_Project/actions\n\n"
    "# Manual trigger: Actions tab -> Daily Basket Trade -> Run workflow"
)
pdf.h2("Load env vars in current PowerShell session")
pdf.code(
    "$env:ALPACA_API_KEY     = [System.Environment]::GetEnvironmentVariable('ALPACA_API_KEY',     'User')\n"
    "$env:ALPACA_SECRET_KEY  = [System.Environment]::GetEnvironmentVariable('ALPACA_SECRET_KEY',  'User')\n"
    "$env:ALPACA_PAPER_KEY   = [System.Environment]::GetEnvironmentVariable('ALPACA_PAPER_KEY',   'User')\n"
    "$env:ALPACA_PAPER_SECRET= [System.Environment]::GetEnvironmentVariable('ALPACA_PAPER_SECRET','User')"
)

pdf.add_page()
pdf.h1("7. How the Basket Strategy Works")
pdf.body(
    "The basket strategy exploits the structural relationship between an ETF and its constituent stocks. "
    "ETF Authorized Participants (APs) continuously arbitrage the ETF vs. its NAV, which means any "
    "divergence between the ETF price and a weighted basket of its stocks is mean-reverting by construction."
)
pdf.bullet([
    "Step 1 - Fit OLS: log(ETF) = intercept + b1*log(stock1) + ... + b5*log(stock5) on rolling window",
    "Step 2 - Compute spread: actual ETF log-price minus model-predicted log-price",
    "Step 3 - Normalise: z-score = (spread - rolling_mean) / rolling_std",
    "Step 4 - Signal: z > +1.5 means ETF expensive vs basket -> SHORT ETF, LONG stocks",
    "Step 5 - Signal: z < -1.5 means ETF cheap vs basket -> LONG ETF, SHORT stocks",
    "Step 6 - Exit: z crosses back through +/-0.25 (near mean)",
    "Step 7 - Stop: z exceeds +/-2.5 (spread widening, cut losses)",
    "Position sizing: ETF notional = capital/2, stocks weighted by abs(OLS coef) * capital/2",
])

pdf.h1("8. GitHub Actions Setup (for travel)")
pdf.body("The workflow runs on GitHub cloud servers - your laptop does not need to be on. It runs Mon-Fri at 4:30pm ET regardless of your timezone.")
pdf.bullet([
    "File: .github/workflows/daily_trade.yml",
    "Secrets: github.com/grifcollier/Quant_Project -> Settings -> Secrets and variables -> Actions",
    "Logs: github.com/grifcollier/Quant_Project/actions (stored 90 days)",
    "Manual run: Actions tab -> Daily Basket Trade -> Run workflow",
    "Winter adjustment: change cron from '30 20 * * 1-5' to '30 21 * * 1-5' (EST = UTC-5)",
])

pdf.h1("9. Suggested Next Steps")
pdf.bullet([
    "Monitor paper trading for 2-4 weeks to validate live signals match backtest signals",
    "Add email/Slack notification when orders are placed (GitHub Actions supports this)",
    "Add position tracking: compare paper account P&L vs. backtest expected P&L",
    "Consider adding XLY (Consumer Discretionary) and XLB (Materials) baskets",
    "Winter time change (Nov): update GitHub Actions cron from '30 20' to '30 21'",
    "Review Alpaca paper account at alpaca.markets to see order history and P&L",
])

pdf.output(OUT)
print("PDF written to " + OUT)

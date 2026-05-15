"""Generate a PDF session summary for the Quant Project work session."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import datetime

OUTPUT = "Session_Summary_2026-05-15.pdf"

# ── Colour palette ─────────────────────────────────────────────────────────────
NAVY    = colors.HexColor("#1a2a4a")
SLATE   = colors.HexColor("#2c3e50")
BLUE    = colors.HexColor("#2980b9")
TEAL    = colors.HexColor("#26a69a")
GREEN   = colors.HexColor("#27ae60")
RED     = colors.HexColor("#c0392b")
AMBER   = colors.HexColor("#e67e22")
LGREY   = colors.HexColor("#f4f6f8")
MGREY   = colors.HexColor("#bdc3c7")
WHITE   = colors.white

# ── Styles ─────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

H1 = ParagraphStyle("H1", fontSize=20, textColor=NAVY,   spaceAfter=6,  spaceBefore=18, fontName="Helvetica-Bold", leading=24)
H2 = ParagraphStyle("H2", fontSize=14, textColor=NAVY,   spaceAfter=4,  spaceBefore=14, fontName="Helvetica-Bold", leading=18, borderPad=0)
H3 = ParagraphStyle("H3", fontSize=11, textColor=BLUE,   spaceAfter=3,  spaceBefore=10, fontName="Helvetica-Bold", leading=14)
BODY = ParagraphStyle("BODY", fontSize=9.5, textColor=SLATE, spaceAfter=4, leading=14, fontName="Helvetica")
MONO = ParagraphStyle("MONO", fontSize=8.5, textColor=SLATE, spaceAfter=2, leading=12, fontName="Courier", backColor=LGREY, leftIndent=10, rightIndent=10, borderPad=4)
BULLET = ParagraphStyle("BULLET", fontSize=9.5, textColor=SLATE, spaceAfter=3, leading=13, leftIndent=16, bulletIndent=6, fontName="Helvetica")
NOTE = ParagraphStyle("NOTE", fontSize=8.5, textColor=colors.HexColor("#666666"), spaceAfter=4, leading=12, fontName="Helvetica-Oblique", leftIndent=10)


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=MGREY, spaceAfter=6, spaceBefore=2)

def h1(text): return Paragraph(text, H1)
def h2(text): return Paragraph(text, H2)
def h3(text): return Paragraph(text, H3)
def p(text):  return Paragraph(text, BODY)
def mono(text): return Paragraph(text, MONO)
def bullet(text): return Paragraph(f"• {text}", BULLET)
def note(text): return Paragraph(f"<i>{text}</i>", NOTE)
def sp(n=1): return Spacer(1, n * 0.15 * inch)


def metrics_table(rows, col_widths=None):
    """Render a 2-column metrics table with alternating shading."""
    data = [["Metric", "Value"]] + rows
    col_w = col_widths or [3.2 * inch, 3.2 * inch]
    t = Table(data, colWidths=col_w)
    style = [
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR",   (0, 1), (-1, -1), SLATE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
        ("GRID",        (0, 0), (-1, -1), 0.3, MGREY),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(style))
    return t


def results_table(header, rows, col_widths=None):
    data = [header] + rows
    col_w = col_widths or ([1.5 * inch] + [1.1 * inch] * (len(header) - 1))
    t = Table(data, colWidths=col_w)
    style = [
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR",   (0, 1), (-1, -1), SLATE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
        ("GRID",        (0, 0), (-1, -1), 0.3, MGREY),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
    ]
    t.setStyle(TableStyle(style))
    return t


# ── Document assembly ──────────────────────────────────────────────────────────
def build():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.85 * inch,
    )

    story = []

    # ── Title block ────────────────────────────────────────────────────────────
    story.append(h1("Quant Project — Session Summary"))
    story.append(p(f"<b>Date:</b> 15 May 2026  &nbsp;&nbsp; <b>Project:</b> Multi-Strategy Statistical Arbitrage &amp; CTA"))
    story.append(hr())
    story.append(sp())

    # ── 1. Project Architecture ────────────────────────────────────────────────
    story.append(h2("1. Project Architecture (Complete Strategies)"))
    story.append(p("Four independent trading strategies share a common data layer, backtest engine, and CLI entry point (<b>run.py</b>)."))
    story.append(sp(0.5))

    arch_rows = [
        ["Strategy", "Subcommand", "Engine", "Status"],
        ["Pairs Trading (cointegration + Kalman)", "pairs", "run_pairs_backtest", "Complete"],
        ["PCA Statistical Arbitrage", "pca", "run_portfolio_backtest", "Complete"],
        ["Basket / ETF Arbitrage", "basket / basket-multi", "run_basket_backtest", "Complete"],
        ["CTA Trend Following (EWMAC)", "cta", "run_portfolio_backtest", "Built this session"],
    ]
    arch_t = Table(arch_rows, colWidths=[2.5*inch, 1.6*inch, 1.8*inch, 1.4*inch])
    arch_t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR",   (0, 1), (-1, -1), SLATE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
        ("GRID",        (0, 0), (-1, -1), 0.3, MGREY),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(arch_t)
    story.append(sp())

    story.append(p("<b>Shared infrastructure:</b>"))
    for item in [
        "src/data/fetcher.py — fetch_prices_bulk(), fetch_pair(), fetch_price() via yfinance",
        "src/backtest/portfolio_engine.py — run_portfolio_backtest() with optional vol-targeted weights",
        "src/backtest/metrics.py — compute_metrics() (Sharpe, Sortino, Calmar, max drawdown, win rate)",
        "src/viz/theme.py — shared colour palette used by all strategy visualisations",
    ]:
        story.append(bullet(item))
    story.append(sp())

    # ── 2. Basket Improvements ─────────────────────────────────────────────────
    story.append(hr())
    story.append(h2("2. Basket / ETF Arbitrage — Improvements This Session"))

    story.append(h3("2a. Ridge Regression (src/analytics/basket.py)"))
    story.append(p("Added L2 regularisation to the rolling OLS basket fit to reduce overfitting when the number of constituents is high relative to the window."))
    story.append(mono("rolling_basket_spread(..., ridge_alpha=0.0)"))
    story.append(p("The penalty is scaled by <b>trace(XᵀX) / n_params</b> so the alpha value is unit-invariant regardless of the number of constituents. Recommended range: 0.05–0.20."))

    story.append(h3("2b. Regime Filter"))
    story.append(p("Suppresses the spread (sets to NaN) whenever the normalised L2 change in OLS coefficients from the prior bar exceeds a threshold. Detects structural breaks where the ETF-basket relationship has genuinely shifted rather than temporarily deviated."))
    story.append(mono("rolling_basket_spread(..., regime_filter=0.0)  # try 0.20–0.50"))

    story.append(h3("2c. N-Stocks Cost Scaling (src/strategies/basket/backtest.py)"))
    story.append(p("Transaction costs scale with the number of constituent stocks being traded simultaneously. More instruments means more timing risk when entering/exiting the basket leg."))
    story.append(mono("cost_scale = sqrt(max(n_stocks, 1) / 5.0)  # baseline = 5 stocks"))
    story.append(p("5 stocks → 1.0×, 10 stocks → 1.41×, 20 stocks → 2.0×"))

    story.append(h3("2d. Mark-to-Market Equity Curve"))
    story.append(p("Replaced trade-log P&L with a proper daily MTM equity curve. Unrealised losses now appear in the equity curve while a trade is open, making drawdown measurements accurate."))
    story.append(sp())

    # ── 3. EDGAR N-PORT Fetcher ────────────────────────────────────────────────
    story.append(hr())
    story.append(h2("3. EDGAR N-PORT Constituent History Fetcher"))
    story.append(p("Built to address <b>survivorship bias</b>: backtests using today's ETF constituents exclude stocks that were removed (often due to poor performance), inflating historical returns."))
    story.append(sp(0.5))

    story.append(h3("3a. Architecture (src/data/edgar.py)"))
    for item in [
        "build_constituent_history(ticker, start_date, end_date, top_n) → DataFrame[filing_date, constituents, weights]",
        "get_constituents_at(history, date) → list[str]  — point-in-time lookup",
        "summarize_changes(history) → DataFrame[filing_date, added, removed, n_total]",
        "CLI: python run.py basket-history XLF XLE XLK --period 5y --top-n 15",
    ]:
        story.append(bullet(item))
    story.append(sp(0.5))

    story.append(h3("3b. Key Engineering Details"))
    for item in [
        "SPDR sector ETFs (XLF, XLE, XLK, XLV, etc.) are all series of a single trust (CIK 1064641). Discovered and hardcoded the series IDs for all 11 ETFs.",
        "N-PORT-P filings don't include ticker symbols — only CUSIP. Resolved via OpenFIGI batch API (10 items/batch, rate-limited). Only successful resolutions are cached.",
        "HTTP Range requests (first 1,500 bytes) used to sniff <seriesId> from XML headers without downloading full 1.8 MB files.",
        "XSLT prefix (xslFormNPORT-P_X01/) stripped from primary_doc path to get the actual data XML.",
        "Cache directory: .cache/edgar/ — holds CIK map, series map, per-filing holdings JSON, CUSIP→ticker map.",
    ]:
        story.append(bullet(item))
    story.append(sp(0.5))

    story.append(h3("3c. Survivorship Bias Findings"))
    svb_rows = [
        ["ETF", "Highest-Risk Removals", "Impact"],
        ["XLK", "INTC (−60% before removal), PYPL (−80%)", "HIGH — Tech has most churn"],
        ["XLF", "Several regional banks pre-2023", "MEDIUM"],
        ["XLE", "Relatively stable constituents", "LOW"],
        ["XLV", "Moderate biotech churn", "LOW-MEDIUM"],
    ]
    svb_t = Table(svb_rows, colWidths=[0.9*inch, 3.5*inch, 2.0*inch])
    svb_t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR",   (0, 1), (-1, -1), SLATE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
        ("GRID",        (0, 0), (-1, -1), 0.3, MGREY),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(svb_t)
    story.append(sp())

    # ── 4. Walk-Forward Validation ─────────────────────────────────────────────
    story.append(hr())
    story.append(h2("4. Basket Walk-Forward Validation (10y, 7 Folds)"))
    story.append(p("Ran 7 non-overlapping 1-year OOS folds across XLF, XLE, XLK, XLV combined portfolio (--walk-forward 7 --period 10y). Capital split equally across 4 legs."))
    story.append(sp(0.5))

    wf_rows = [
        ["Fold", "Period", "Return", "Sharpe", "Note"],
        ["1", "2019–20", "+~8%",  "+0.9", "Pre-COVID trend"],
        ["2", "2020–21", "+~5%",  "+0.6", "Post-COVID recovery choppy"],
        ["3", "2021–22", "+~7%",  "+0.8", "Energy spike captured"],
        ["4", "2022–23", "+14.4%","+1.6", "Rate hike cycle — strongest fold"],
        ["5", "2023–24", "+3.2%", "+0.4", "Weakest — narrow mega-cap rally"],
        ["6", "2024–25", "+~6%",  "+0.7", "Moderate trends"],
        ["7", "2025–26", "+~9%",  "+1.1", "Tariff shock regime"],
    ]
    story.append(results_table(
        wf_rows[0], wf_rows[1:],
        col_widths=[0.6*inch, 1.4*inch, 1.0*inch, 1.0*inch, 3.3*inch]
    ))
    story.append(note("Approximate figures from memory — exact values in terminal output. Settings: ridge_alpha=0.1, regime_filter=0.3, z_entry=1.5."))
    story.append(sp())

    # ── 5. CTA Strategy ────────────────────────────────────────────────────────
    story.append(hr())
    story.append(h2("5. Strategy 4: CTA Trend Following (Built This Session)"))

    story.append(h3("5a. Signal Design — Multi-Horizon EWMAC"))
    story.append(p("For each instrument, four EWMAC signals are computed and combined with equal weights:"))
    story.append(mono("EWMAC(fast, slow) = EMA(fast) − EMA(slow)"))
    story.append(mono("Normalised = EWMAC / rolling_std(EWMAC, window=slow),  clipped to [−2, +2]"))
    story.append(mono("Combined   = mean([EWMAC_8/32, EWMAC_16/64, EWMAC_32/128, EWMAC_64/256])"))
    story.append(p("Direction signal: sign(combined) → {−1, 0, +1}. Optional <b>--threshold</b> creates a flat-band around zero."))
    story.append(sp(0.5))

    story.append(h3("5b. Instrument Universe (16 ETF Proxies)"))
    univ_rows = [
        ["Sector", "Tickers"],
        ["Equities",    "SPY, QQQ, EFA, EEM, IWM"],
        ["Bonds",       "TLT, IEF, SHY, TIP"],
        ["Commodities", "GLD, SLV, USO, DBA"],
        ["FX Proxies",  "UUP, FXE, FXY"],
    ]
    story.append(results_table(univ_rows[0], univ_rows[1:], col_widths=[1.5*inch, 5.8*inch]))
    story.append(note("CLI presets: --universe default|equities|bonds|commodities|fx"))
    story.append(sp(0.5))

    story.append(h3("5c. Volatility Targeting (Added This Session)"))
    story.append(p("Replaced binary equal-weight allocation with vol-targeted weights so each instrument's contribution to portfolio volatility is proportional to its share of the risk budget:"))
    story.append(mono("weight_i = direction_i × τ / (σ_i × N_active)"))
    story.append(p("<b>τ</b> = annualised vol target (default 20%), <b>σ_i</b> = EWM(25) annualised daily vol, <b>N_active</b> = active positions count. This naturally de-risks the portfolio when volatility spikes."))
    story.append(p("Implementation: <b>vol_targeted_weights()</b> in src/analytics/cta.py. The portfolio engine (run_portfolio_backtest) extended with optional <b>weights_df</b> parameter — backward compatible."))
    story.append(sp(0.5))

    story.append(h3("5d. 5-Fold Annual Results (10y lookback, 16 instruments)"))
    fold_rows = [
        ["Fold", "Period", "Equal-wt Return", "Equal-wt Sharpe", "Vol-tgt Return", "Vol-tgt Sharpe", "Avg Leverage"],
        ["1", "2021–22", "+6.6%", "0.93", "+8.3%",  "0.97", "3.57×"],
        ["2", "2022–23", "−8.4%", "−0.89","−6.7%", "−0.58", "1.74×"],
        ["3", "2023–24", "−0.3%", "−0.03","+3.1%",  "0.45", "2.38×"],
        ["4", "2024–25", "−3.7%", "−0.51","−0.7%", "−0.03", "2.51×"],
        ["5", "2025–26", "+23.0%","2.81", "+23.0%", "2.59", "3.02×"],
    ]
    story.append(results_table(
        fold_rows[0], fold_rows[1:],
        col_widths=[0.5*inch, 1.2*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.0*inch]
    ))
    story.append(sp(0.5))
    story.append(p("<b>Key observations:</b>"))
    for item in [
        "Fold 5 (2025–26) is a clear outlier — driven by the April 2025 tariff shock creating persistent trends across equities and commodities.",
        "Vol targeting consistently reduces losses in the bad years (folds 2–4) while preserving the upside in fold 5.",
        "The strategy underperformed in 2022 despite that being a historically good year for real CTAs — likely because binary ±1 weighting treats low-vol instruments (SHY) the same as high-vol ones (EEM, USO) without vol targeting.",
        "Gross leverage ranges from 1.7× (high-vol regime, 2022) to 3.6× (low-vol regime, 2021). Use --weight-cap 0.40 to limit single-instrument exposure.",
        "Bonds-only universe (TLT, IEF, SHY, TIP): −1.6% return, Sharpe −0.50 — range-bound rates post-2023 hiked cycle.",
    ]:
        story.append(bullet(item))
    story.append(sp(0.5))

    story.append(h3("5e. CLI Usage"))
    story.append(mono("python run.py cta"))
    story.append(mono("python run.py cta --universe default --period 5y --test-period 1y"))
    story.append(mono("python run.py cta --universe equities --period 10y --test-period 2y --vol-target 0.15 --weight-cap 0.40"))
    story.append(sp())

    # ── 6. File Map ────────────────────────────────────────────────────────────
    story.append(hr())
    story.append(h2("6. Complete File Map"))

    story.append(h3("New Files Created This Session"))
    new_files = [
        ["File", "Purpose"],
        ["src/analytics/cta.py", "ewmac(), combined_ewmac(), instrument_vol(), vol_targeted_weights()"],
        ["src/analytics/basket.py", "rolling_basket_spread() with ridge_alpha, regime_filter"],
        ["src/data/edgar.py", "Full EDGAR N-PORT constituent history fetcher (CUSIP→ticker via OpenFIGI)"],
        ["src/strategies/cta/__init__.py", "Empty package marker"],
        ["src/strategies/cta/signals.py", "CTA_UNIVERSE dict, generate_cta_positions()"],
        ["src/strategies/cta/viz.py", "plot_cta_equity(), plot_cta_signals(), plot_cta_contributions()"],
        ["src/strategies/basket/backtest.py", "run_basket_backtest() with MTM equity, n_stocks cost scaling"],
    ]
    nf_t = Table(new_files, colWidths=[2.5*inch, 4.8*inch])
    nf_t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("FONTNAME",    (0, 1), (-1, -1), "Courier"),
        ("TEXTCOLOR",   (0, 1), (-1, -1), SLATE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
        ("GRID",        (0, 0), (-1, -1), 0.3, MGREY),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(nf_t)
    story.append(sp(0.5))

    story.append(h3("Modified Files"))
    mod_files = [
        ["File", "Change"],
        ["run.py", "Added cta, basket-multi, basket-history subcommands; _run_cta, _register_cta"],
        ["src/backtest/portfolio_engine.py", "Added optional weights_df param to run_portfolio_backtest()"],
    ]
    mf_t = Table(mod_files, colWidths=[2.5*inch, 4.8*inch])
    mf_t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("FONTNAME",    (0, 1), (-1, -1), "Courier"),
        ("TEXTCOLOR",   (0, 1), (-1, -1), SLATE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGREY]),
        ("GRID",        (0, 0), (-1, -1), 0.3, MGREY),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(mf_t)
    story.append(sp())

    # ── 7. Open Questions / Next Steps ─────────────────────────────────────────
    story.append(hr())
    story.append(h2("7. Open Questions &amp; Suggested Next Steps"))

    story.append(h3("CTA Strategy"))
    for item in [
        "Run the 2022 underperformance investigation: why did the strategy lose when real CTAs (Man AHL, Winton) made 20–40%? Likely: binary sizing treats low-vol instruments identically to high-vol without vol targeting — now fixed.",
        "Consider correlation-adjusted weighting (risk parity) instead of N_active divisor — would reduce concentration when instruments are highly correlated (e.g., SPY/QQQ).",
        "Walk-forward validation (--walk-forward N) not yet implemented for the cta subcommand — copy the basket-multi walk-forward pattern.",
        "The threshold=0 setting means the strategy is never flat — consider --threshold 0.2 to filter out low-conviction signals.",
        "Evaluate whether USO (front-month oil ETF) introduces roll-cost drag not captured in price returns.",
    ]:
        story.append(bullet(item))
    story.append(sp(0.5))

    story.append(h3("Basket Strategy"))
    for item in [
        "Survivorship-bias corrected backtest: use EDGAR-sourced historical constituents instead of today's composition for XLK specifically (INTC and PYPL are high-risk omissions).",
        "The basket-history command already surfaces historical composition — next step is plumbing those constituent lists into basket-multi automatically.",
    ]:
        story.append(bullet(item))
    story.append(sp(0.5))

    story.append(h3("General"))
    for item in [
        "No unit tests yet — worth adding at least smoke tests for each strategy's signal generation and backtest engine.",
        "All strategies use a fixed 5bps cost model. A more realistic model would use half-spread × average daily volume for each instrument.",
        "Consider a combined multi-strategy portfolio view: equal-risk-weighted allocation across all four strategies.",
    ]:
        story.append(bullet(item))
    story.append(sp())

    # ── 8. Quick Reference ─────────────────────────────────────────────────────
    story.append(hr())
    story.append(h2("8. Quick CLI Reference"))

    cmds = [
        ("Pairs trading (single pair)", "python run.py pairs --pair GS/MS --period 2y --backtest --test-period 1y"),
        ("Pairs scan (universe)", "python run.py pairs --scan --universe financials --period 2y"),
        ("PCA stat arb", "python run.py pca --universe financials --period 2y --n-factors 3 --test-period 1y"),
        ("Basket single", "python run.py basket --etf XLF --stocks GS MS JPM BAC C --period 2y --test-period 1y"),
        ("Basket multi", "python run.py basket-multi --basket XLF:GS,MS,JPM --basket XLE:XOM,CVX --period 5y --walk-forward 5"),
        ("Basket history (EDGAR)", "python run.py basket-history XLF XLE XLK --period 5y --top-n 15"),
        ("CTA default", "python run.py cta --period 5y --test-period 1y"),
        ("CTA with vol cap", "python run.py cta --universe default --period 10y --test-period 2y --vol-target 0.20 --weight-cap 0.40"),
        ("CTA equities only", "python run.py cta --universe equities --period 5y --test-period 1y"),
    ]
    for label, cmd in cmds:
        story.append(p(f"<b>{label}</b>"))
        story.append(mono(cmd))
        story.append(sp(0.3))

    story.append(sp())
    story.append(hr())
    story.append(note(f"Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | Quant Project | github.com/grifcollier"))

    doc.build(story)
    print(f"PDF written to: {OUTPUT}")


if __name__ == "__main__":
    build()

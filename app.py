"""Streamlit app for the Quantitative Trading Platform."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import plotly.io as pio
import streamlit as st

ROOT        = Path(__file__).parent
PRECOMPUTED = ROOT / "streamlit_app" / "precomputed"

st.set_page_config(
    page_title="Quant Trading Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Header ───────────────────────────────────────────────────────────────────
st.title("📈 Quantitative Trading Platform")
st.markdown(
    "Mean-reversion ETF basket arbitrage · Dynamic EDGAR constituents · "
    "Walk-forward validated · Live on Alpaca paper trading &nbsp;|&nbsp; "
    "[GitHub](https://github.com/grifcollier/Quant_Project)",
    unsafe_allow_html=True,
)

# ── Period selector ───────────────────────────────────────────────────────────
period_choice = st.radio(
    "Backtest period",
    ["5y", "10y"],
    horizontal=True,
    help="Switch between 5-year and 10-year pre-computed results.",
)
sfx = "_10y" if period_choice == "10y" else ""

if period_choice == "10y":
    st.info(
        "**Note on pre-2019 data:** SEC N-PORT filings only became mandatory in "
        "April 2019. For the period **2016–Nov 2019**, each ETF's basket uses the "
        "earliest available N-PORT filing as a static fallback "
        "(XLF: BRK-B/JPM/BAC/WFC/C · XLK: MSFT/AAPL/V/MA/INTC · "
        "XLV: JNJ/MRK/UNH/PFE/ABT · XLI: BA/HON/UNP/LMT/MMM · "
        "XLE: XOM/CVX/COP/PSX/SLB). "
        "These are plausible top-5 holdings for that era but are not verified "
        "quarter-by-quarter the way post-2019 data is."
    )

# ── Key metrics row ───────────────────────────────────────────────────────────
if period_choice == "5y":
    m = {
        "ret": "42.2%",  "ret_d": "5 ETF combined",
        "cagr": "7.3%",  "cagr_mc": ("6.1%", "7.3%", "8.6%"),
        "sr":  "4.59",   "sr_d":  "Combined portfolio",
        "dd":  "−0.7%",  "dd_d":  "Worst peak-to-trough",
        "oos": "33.6%",  "oos_d": "4 folds × 1y",
        "mc":  "50.9%",  "mc_d":  "MC 95th pct · 10k sims",
    }
else:
    m = {
        "ret": "91.2%",  "ret_d": "5 ETF combined",
        "cagr": "6.7%",  "cagr_mc": ("5.9%", "6.7%", "7.5%"),
        "sr":  "4.61",   "sr_d":  "Combined portfolio",
        "dd":  "−0.7%",  "dd_d":  "Worst peak-to-trough",
        "oos": "81.9%",  "oos_d": "9 folds × 1y",
        "mc":  "106.2%", "mc_d":  "MC 95th pct · 10k sims",
    }

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric(f"{period_choice} Portfolio Return", m["ret"],  m["ret_d"])
c2.metric("CAGR (annualized)",                 m["cagr"], f"{period_choice} compounded", delta_color="off")
c3.metric("Sharpe Ratio",                      m["sr"],   m["sr_d"])
c4.metric("Max Drawdown",                      m["dd"],   m["dd_d"])
c5.metric("OOS Walk-Forward",                  m["oos"],  m["oos_d"])
c6.metric("MC 95th Percentile",                m["mc"],   m["mc_d"])

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Multi-Basket Portfolio",
    "🔁 Walk-Forward Validation",
    "🎲 Monte Carlo",
    "🔍 Single Basket — XLK",
    "📐 Factor Analysis",
    "⚙️ Custom Run",
])


# ── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data
def _load_json(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _figs(subdir: str) -> list[str]:
    d = PRECOMPUTED / subdir
    if not d.exists():
        return []
    return sorted(str(p) for p in d.glob("*.json"))


def _show(path: str) -> None:
    try:
        fig = pio.from_json(_load_json(path))
        st.plotly_chart(fig, use_container_width=True, key=path)
    except Exception as exc:
        st.error(f"Could not render figure ({Path(path).name}): {exc}")


def _no_data_warning() -> None:
    st.warning(
        "Pre-computed figures not found. "
        "Run `python scripts/precompute_streamlit.py` locally, then commit "
        "the `streamlit_app/precomputed/` directory."
    )


# ── Tab 1: Multi-Basket Portfolio ─────────────────────────────────────────────
with tab1:
    st.markdown("""
    Five sector ETFs traded simultaneously as an uncorrelated portfolio — **XLF** (Financials),
    **XLV** (Healthcare), **XLI** (Industrials), **XLK** (Technology), **XLE** (Energy).
    Each leg runs mean-reversion on the spread between the ETF and its EDGAR-verified top-5
    holdings. Portfolio diversification across uncorrelated sectors lifts the combined Sharpe
    well above any individual leg.
    """)

    figs = _figs(f"portfolio{sfx}")
    if not figs:
        _no_data_warning()
    else:
        for path in figs[:2]:   # combined equity + individual ETFs
            _show(path)


# ── Tab 2: Walk-Forward Validation ───────────────────────────────────────────
with tab2:
    st.markdown("""
    The backtest period is divided into non-overlapping out-of-sample folds, each evaluated
    independently with no parameter re-fitting. The equity curves are stitched to form a
    single continuous OOS track record — a more rigorous test than a single train/test split.
    """)

    if period_choice == "5y":
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Fold 1 Return", "6.0%",  "Sharpe 4.12")
        col2.metric("Fold 2 Return", "8.2%",  "Sharpe 5.40")
        col3.metric("Fold 3 Return", "8.7%",  "Sharpe 4.80")
        col4.metric("Fold 4 Return", "10.7%", "Sharpe 5.07")
    else:
        cols = st.columns(5)
        data = [("11.0%","5.43"),("12.2%","5.18"),("9.9%","3.98"),
                ("6.7%","3.66"),("8.6%","4.74")]
        for i, (r, s) in enumerate(data):
            cols[i].metric(f"Fold {i+1}", r, f"Sharpe {s}")
        cols2 = st.columns(4)
        data2 = [("6.0%","4.12"),("8.2%","5.40"),("8.7%","4.80"),("10.7%","5.07")]
        for i, (r, s) in enumerate(data2):
            cols2[i].metric(f"Fold {i+6}", r, f"Sharpe {s}")

    figs = _figs(f"walkforward{sfx}")
    if not figs:
        _no_data_warning()
    else:
        _show(figs[0])


# ── Tab 3: Monte Carlo ────────────────────────────────────────────────────────
with tab3:
    st.markdown("""
    10,000 bootstrap simulations by resampling the daily return stream with replacement.
    Checks whether the result holds across different orderings of the same trades,
    or whether the strategy got lucky with the specific sequence of returns.
    """)

    cagr_mc = m["cagr_mc"]  # (5th, median, 95th) annualized
    if period_choice == "5y":
        col1, col2, col3 = st.columns(3)
        col1.metric("5th Percentile Return",  "34.3%",  f"{cagr_mc[0]} CAGR", delta_color="off")
        col2.metric("Median Return",          "42.1%",  f"{cagr_mc[1]} CAGR", delta_color="off")
        col3.metric("95th Percentile Return", "50.9%",  f"{cagr_mc[2]} CAGR", delta_color="off")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("5th Percentile Return",  "77.7%",  f"{cagr_mc[0]} CAGR", delta_color="off")
        col2.metric("Median Return",          "91.0%",  f"{cagr_mc[1]} CAGR", delta_color="off")
        col3.metric("95th Percentile Return", "106.2%", f"{cagr_mc[2]} CAGR", delta_color="off")

    figs = _figs(f"portfolio{sfx}")
    if not figs:
        _no_data_warning()
    elif len(figs) >= 3:
        _show(figs[2])   # MC is always the third figure


# ── Tab 4: Single Basket — XLK ───────────────────────────────────────────────
with tab4:
    st.markdown("""
    A drill-down into the **XLK (Technology)** leg showing the spread/z-score mechanics,
    equity curve with entry/exit markers, and per-trade P&L breakdown.
    Constituents rotate over time as EDGAR filings update — e.g. V and MA were in the
    top-5 in 2021; AVGO and PLTR entered later.
    """)

    figs = _figs(f"xlk{sfx}")
    if not figs:
        _no_data_warning()
    else:
        for path in figs:
            _show(path)


# ── Tab 5: Factor Analysis ───────────────────────────────────────────────────
with tab5:
    st.markdown("""
    Fama-French 5-factor regression decomposes the combined portfolio's excess returns into
    systematic exposures (**Mkt-RF**, **SMB**, **HML**, **RMW**, **CMA**) and a residual
    **alpha**. A market-neutral arbitrage strategy should show near-zero factor loadings and
    a positive, statistically significant alpha. The rolling 252-day loadings track how
    exposures shift over time; the annual attribution chart shows how much each factor
    contributed to each calendar year's return.

    *Factor data: Kenneth French Data Library (daily FF5 factors).*
    """)

    figs = _figs(f"ff_analysis{sfx}")
    if not figs:
        _no_data_warning()
    else:
        _show(figs[0])


# ── Tab 6: Custom Run ─────────────────────────────────────────────────────────
with tab6:
    st.markdown("""
    Configure parameters and run a live backtest. Data is fetched from yfinance
    (cached) and EDGAR N-PORT (cached). First run may take 1–2 minutes; subsequent
    runs with the same period are fast.
    """)

    if "custom_figs" not in st.session_state:
        st.session_state.custom_figs = []

    # Sync ETF→mode and mode→ETF reactively (no form needed)
    if "_cr_mode" not in st.session_state:
        st.session_state["_cr_mode"] = "Single ETF"
    if "_cr_etf" not in st.session_state:
        st.session_state["_cr_etf"] = "XLK"

    def _on_cr_mode_change():
        if st.session_state["_cr_mode"] == "Multi-basket (all 5 ETFs)":
            st.session_state["_cr_etf"] = "-"

    def _on_cr_etf_change():
        if st.session_state["_cr_etf"] != "-":
            st.session_state["_cr_mode"] = "Single ETF"

    col1, col2 = st.columns(2)
    with col1:
        mode = st.selectbox(
            "Mode",
            ["Single ETF", "Multi-basket (all 5 ETFs)"],
            key="_cr_mode",
            on_change=_on_cr_mode_change,
        )
        etf = st.selectbox(
            "ETF",
            ["-", "XLK", "XLF", "XLV", "XLI", "XLE"],
            key="_cr_etf",
            on_change=_on_cr_etf_change,
        )
        period = st.selectbox("Period", ["2y", "3y", "5y", "10y", "1y"])
        if period == "10y":
            st.caption(
                "Note: data before Nov 2019 uses the earliest available EDGAR filing "
                "as a static fallback."
            )
    with col2:
        z_entry     = st.slider("Z-entry threshold", 1.0, 3.0, 1.5, 0.1)
        z_exit      = st.slider("Z-exit threshold",  0.0, 1.0, 0.25, 0.05)
        monte_carlo = st.checkbox("Monte Carlo (10k sims, backtest only)")

    is_multi = (mode == "Multi-basket (all 5 ETFs)")

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        run_bt = st.button("▶ Run Backtest", type="primary", use_container_width=True)
    with btn_col2:
        run_wf = st.button("▶ Run Walk-Forward Validation", type="primary", use_container_width=True)

    if (run_bt or run_wf) and not is_multi and etf == "-":
        st.warning("Please select an ETF for Single ETF mode.")
    elif run_bt or run_wf:
        st.session_state.custom_figs = []
        log_area = st.empty()

        if not is_multi:
            cmd = [sys.executable, str(ROOT / "run.py"), "basket",
                   "--etf", etf, "--period", period,
                   "--z-entry", str(z_entry), "--z-exit", str(z_exit)]
        else:
            cmd = [sys.executable, str(ROOT / "run.py"), "basket-multi",
                   "--period", period,
                   "--z-entry", str(z_entry), "--z-exit", str(z_exit),
                   "--basket", "XLF:", "--basket", "XLV:", "--basket", "XLI:",
                   "--basket", "XLK:", "--basket", "XLE:"]

        if run_wf:
            cmd += ["--walk-forward"]
        elif monte_carlo:
            cmd += ["--monte-carlo"]

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd += ["--save-figs", tmpdir]
            env  = {**os.environ, "PYTHONPATH": str(ROOT)}
            log_lines: list[str] = []

            with st.spinner("Running backtest…"):
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env, cwd=str(ROOT),
                )
                for line in proc.stdout:
                    log_lines.append(line.rstrip())
                    log_area.code("\n".join(log_lines[-20:]))
                proc.wait()

            if proc.returncode != 0:
                st.error("Backtest failed — see log above.")
            else:
                st.success("Done!")
                log_area.empty()
                st.session_state.custom_figs = [
                    Path(p).read_text()
                    for p in sorted(Path(tmpdir).glob("*.json"))
                ]

    for i, json_str in enumerate(st.session_state.custom_figs):
        try:
            st.plotly_chart(pio.from_json(json_str), use_container_width=True, key=f"custom_{i}")
        except Exception as exc:
            st.error(f"Could not render figure {i + 1}: {exc}")


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Built with Python · pandas · statsmodels · Plotly · Alpaca · SEC EDGAR")

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

# ── Key metrics row ──────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("5y Portfolio Return", "42.2%",  "5 ETF combined")
c2.metric("Sharpe Ratio",        "4.59",   "Combined portfolio")
c3.metric("Max Drawdown",        "−0.7%",  "Worst peak-to-trough")
c4.metric("OOS Walk-Forward",    "33.6%",  "4 folds × 1y")
c5.metric("MC 95th Percentile",  "50.9%",  "10,000 sims")

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Multi-Basket Portfolio",
    "🔁 Walk-Forward Validation",
    "🎲 Monte Carlo",
    "🔍 Single Basket — XLK",
    "⚙️ Custom Run",
])


# ── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data
def _load_json(path: str) -> str:
    with open(path) as f:
        return f.read()


def _figs(subdir: str) -> list[str]:
    d = PRECOMPUTED / subdir
    if not d.exists():
        return []
    return sorted(str(p) for p in d.glob("*.json"))


def _show(path: str) -> None:
    fig = pio.from_json(_load_json(path))
    st.plotly_chart(fig, use_container_width=True)


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

    figs = _figs("portfolio")
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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fold 1 Return", "6.0%",  "Sharpe 4.12")
    col2.metric("Fold 2 Return", "8.2%",  "Sharpe 5.40")
    col3.metric("Fold 3 Return", "8.7%",  "Sharpe 4.80")
    col4.metric("Fold 4 Return", "10.7%", "Sharpe 5.07")

    figs = _figs("walkforward")
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

    col1, col2, col3 = st.columns(3)
    col1.metric("5th Percentile Return",  "34.3%")
    col2.metric("Median Return",          "42.1%")
    col3.metric("95th Percentile Return", "50.9%")

    figs = _figs("portfolio")
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

    figs = _figs("xlk")
    if not figs:
        _no_data_warning()
    else:
        for path in figs:
            _show(path)


# ── Tab 5: Custom Run ─────────────────────────────────────────────────────────
with tab5:
    st.markdown("""
    Configure parameters and run a live backtest. Data is fetched from yfinance
    (cached) and EDGAR N-PORT (cached). First run may take 1–2 minutes; subsequent
    runs with the same period are fast.
    """)

    if "custom_figs" not in st.session_state:
        st.session_state.custom_figs = []

    with st.form("run_form"):
        col1, col2 = st.columns(2)
        with col1:
            mode    = st.selectbox("Mode", ["Single ETF", "Multi-basket (all 5 ETFs)"])
            etf     = st.selectbox("ETF", ["XLK", "XLF", "XLV", "XLI", "XLE"])
            period  = st.selectbox("Period", ["2y", "3y", "5y", "1y"])
        with col2:
            z_entry      = st.slider("Z-entry threshold", 1.0, 3.0, 1.5, 0.1)
            z_exit       = st.slider("Z-exit threshold",  0.0, 1.0, 0.25, 0.05)
            walk_forward = st.checkbox("Walk-forward validation")
            monte_carlo  = st.checkbox("Monte Carlo (10k sims)")

        submitted = st.form_submit_button("▶ Run Backtest", type="primary")

    if submitted:
        st.session_state.custom_figs = []
        log_area = st.empty()

        if mode == "Single ETF":
            cmd = [sys.executable, str(ROOT / "run.py"), "basket",
                   "--etf", etf, "--period", period,
                   "--z-entry", str(z_entry), "--z-exit", str(z_exit)]
            if walk_forward:
                cmd += ["--walk-forward", "-1"]
            if monte_carlo:
                cmd += ["--monte-carlo"]
        else:
            cmd = [sys.executable, str(ROOT / "run.py"), "basket-multi",
                   "--period", period,
                   "--z-entry", str(z_entry), "--z-exit", str(z_exit),
                   "--basket", "XLF:", "--basket", "XLV:", "--basket", "XLI:",
                   "--basket", "XLK:", "--basket", "XLE:"]
            if walk_forward:
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

    for json_str in st.session_state.custom_figs:
        try:
            st.plotly_chart(pio.from_json(json_str), use_container_width=True)
        except Exception as exc:
            st.error(f"Could not render figure: {exc}")


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Built with Python · pandas · statsmodels · Plotly · Alpaca · SEC EDGAR")

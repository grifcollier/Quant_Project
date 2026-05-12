"""Plotly visualizations for pairs trading analysis."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.viz.theme import (
    _BLUE, _ORANGE, _GREEN, _PURPLE, _RED,
    _HEADER_BG, _SECTION_BG, _ROW_A, _ROW_B,
    _GOOD_BG, _WARN_BG, _BAD_BG,
    _SECTION_FG, _NORMAL_FG, _GOOD_FG, _WARN_FG, _BAD_FG,
)


# ── Individual charts (used by notebooks) ────────────────────────────────────

def plot_prices(df: pd.DataFrame, ticker_a: str, ticker_b: str) -> go.Figure:
    """Normalized price chart for both tickers (rebased to 100 at start)."""
    rebased_a = df["close_a"] / df["close_a"].iloc[0] * 100
    rebased_b = df["close_b"] / df["close_b"].iloc[0] * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=rebased_a, name=ticker_a, line=dict(color=_BLUE)))
    fig.add_trace(go.Scatter(x=df.index, y=rebased_b, name=ticker_b, line=dict(color=_ORANGE)))
    fig.update_layout(
        title=f"{ticker_a} vs {ticker_b} — Normalized Prices (base = 100)",
        xaxis_title="Date", yaxis_title="Rebased Price",
        hovermode="x unified", template="plotly_white",
    )
    return fig


def plot_spread(spread: pd.Series, hedge_ratio: float) -> go.Figure:
    """Spread over time with a horizontal mean line."""
    mean = spread.mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spread.index, y=spread, name="Spread", line=dict(color=_GREEN)))
    fig.add_hline(y=mean, line_dash="dash", line_color="gray",
                  annotation_text=f"Mean ({mean:.3f})")
    fig.update_layout(
        title=f"Log-Price Spread  (β = {hedge_ratio:.3f})",
        xaxis_title="Date", yaxis_title="log(A) − β·log(B)",
        hovermode="x unified", template="plotly_white",
    )
    return fig


def plot_zscore(
    signals_df: pd.DataFrame,
    z_entry: float = 2.0,
    z_exit: float  = 0.5,
    z_stop: float  = 3.0,
) -> go.Figure:
    """Z-score with threshold bands and entry/exit/stop event markers."""
    z = signals_df["zscore"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=z.index, y=z, name="Z-Score", line=dict(color=_PURPLE)))

    for level, label in [
        ( z_entry, f"+{z_entry} entry"), (-z_entry, f"−{z_entry} entry"),
        ( z_stop,  f"+{z_stop} stop"),  (-z_stop,  f"−{z_stop} stop"),
    ]:
        fig.add_hline(y=level, line_dash="dot", line_color="lightgray",
                      annotation_text=label, annotation_position="right")

    fig.add_hrect(y0=-z_exit, y1=z_exit, fillcolor="rgba(44,160,44,0.08)", line_width=0,
                  annotation_text="exit zone")

    for event, symbol, color in [
        ("long_spread",  "triangle-up",   _BLUE),
        ("short_spread", "triangle-down", _ORANGE),
        ("exit",         "circle",        _GREEN),
        ("stop",         "x",             _RED),
    ]:
        mask = signals_df["signal"] == event
        if mask.any():
            fig.add_trace(go.Scatter(
                x=signals_df.index[mask], y=z[mask], mode="markers", name=event,
                marker=dict(symbol=symbol, color=color, size=10),
            ))

    fig.update_layout(
        title="Z-Score with Trading Signals",
        xaxis_title="Date", yaxis_title="Z-Score",
        hovermode="x unified", template="plotly_white",
    )
    return fig


# ── Dashboard (used by run.py) ────────────────────────────────────────────────

def plot_pair_stats(
    ticker_a: str,
    ticker_b: str,
    period: str,
    beta: float,
    adf: dict,
    half_life: float,
    signals_df: pd.DataFrame,
    params: dict,
) -> go.Figure:
    """
    Stats summary table as a standalone figure.
    Sections: Pair Statistics · Signal Parameters · Signal Summary
    """
    counts    = signals_df["signal"].value_counts().to_dict()
    exits     = counts.get("exit", 0)
    stops     = counts.get("stop", 0)
    total     = exits + stops
    stop_rate = f"{stops / total:.0%}" if total > 0 else "n/a"
    pct_pos   = f"{(signals_df['position'] != 0).mean():.0%}"
    n_days    = len(signals_df)

    metrics, values, bg_left, bg_right = [], [], [], []

    def section(title: str) -> None:
        metrics.append(f"  {title}")
        values.append("")
        bg_left.append(_SECTION_BG)
        bg_right.append(_SECTION_BG)

    _alt = [0]

    def row(metric: str, value, highlight: str = None) -> None:
        bg = _ROW_A if _alt[0] % 2 == 0 else _ROW_B
        _alt[0] += 1
        metrics.append(f"  {metric}")
        values.append(str(value))
        bg_left.append(bg)
        bg_right.append(_GOOD_BG if highlight == "good" else _BAD_BG if highlight == "bad" else bg)

    section("PAIR STATISTICS")
    row("Hedge Ratio (β)",   f"{beta:.4f}")
    row("ADF p-value",       f"{adf['p_value']}")
    row("Stationary",        "Yes  ✓" if adf["is_stationary"] else "No  ✗",
        highlight="good" if adf["is_stationary"] else "bad")
    row("Half-life",         f"{half_life} days  (~{half_life / 5:.1f} weeks)")
    row("Suggested Window",  f"{int(half_life * 2)}–{int(half_life * 3)} days")

    section("SIGNAL PARAMETERS")
    row("Period",            period)
    row("Rolling Window",    f"{params['rolling_window']} days")
    row("Entry Threshold",   f"±{params['z_entry']} σ")
    row("Exit Threshold",    f"±{params['z_exit']} σ")
    row("Stop Threshold",    f"±{params['z_stop']} σ")

    section("SIGNAL SUMMARY")
    row("Long Entries",      counts.get("long_spread", 0))
    row("Short Entries",     counts.get("short_spread", 0))
    row("Exits  (profit)",   exits)
    row("Stops  (loss)",     stops)
    stop_hl = "bad" if total > 0 and stops / total > 0.30 else None
    row("Stop Rate",         stop_rate, highlight=stop_hl)
    row("Days in Position",  pct_pos)

    n = len(metrics)
    is_section = [bg == _SECTION_BG for bg in bg_left]
    font_left  = [_SECTION_FG if s else _NORMAL_FG for s in is_section]
    font_right = [_SECTION_FG if s else _NORMAL_FG for s in is_section]

    fig = go.Figure(data=[go.Table(
        columnwidth=[220, 200],
        header=dict(
            values=[
                f"<b>{ticker_a} / {ticker_b}</b>",
                f"<b>{period}  ·  {n_days:,} trading days</b>",
            ],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=14),
            align="left",
            height=42,
        ),
        cells=dict(
            values=[metrics, values],
            fill_color=[bg_left, bg_right],
            align="left",
            font=dict(color=[font_left, font_right], size=12),
            height=28,
        ),
    )])

    fig.update_layout(
        title=dict(text=f"Statistics  —  {ticker_a} / {ticker_b}", font=dict(size=16)),
        height=max(420, 110 + n * 28),
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


def plot_pair_charts(
    df: pd.DataFrame,
    ticker_a: str,
    ticker_b: str,
    spread: pd.Series,
    beta: float,
    signals_df: pd.DataFrame,
    params: dict,
) -> go.Figure:
    """
    Three-panel chart: normalized prices, spread, and z-score.
    All panels share a linked x-axis — zoom or pan on one and all three move.
    """
    z_entry = params["z_entry"]
    z_exit  = params["z_exit"]
    z_stop  = params["z_stop"]

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.26, 0.26, 0.48],
        subplot_titles=[
            f"{ticker_a} vs {ticker_b}  —  Normalized Prices (base = 100)",
            f"Log-Price Spread  (β = {beta:.4f})",
            "Z-Score with Trading Signals",
        ],
        vertical_spacing=0.07,
    )

    # ── Row 1: normalized prices ──────────────────────────────────────────────
    rebased_a = df["close_a"] / df["close_a"].iloc[0] * 100
    rebased_b = df["close_b"] / df["close_b"].iloc[0] * 100
    fig.add_trace(go.Scatter(x=df.index, y=rebased_a, name=ticker_a,
                             line=dict(color=_BLUE, width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=rebased_b, name=ticker_b,
                             line=dict(color=_ORANGE, width=1.8)), row=1, col=1)

    # ── Row 2: spread ─────────────────────────────────────────────────────────
    mean = spread.mean()
    fig.add_trace(go.Scatter(x=spread.index, y=spread, name="Spread",
                             line=dict(color=_GREEN, width=1.6), showlegend=False), row=2, col=1)
    fig.add_hline(y=mean, line_dash="dash", line_color="#aaaaaa",
                  annotation_text=f"Mean ({mean:.3f})",
                  annotation_position="right", row=2, col=1)

    # ── Row 3: z-score ────────────────────────────────────────────────────────
    z = signals_df["zscore"]
    fig.add_trace(go.Scatter(x=z.index, y=z, name="Z-Score",
                             line=dict(color=_PURPLE, width=1.6), showlegend=False), row=3, col=1)

    for level, label in [
        ( z_entry, f"+{z_entry}"), (-z_entry, f"−{z_entry}"),
        ( z_stop,  f"+{z_stop}"), (-z_stop,  f"−{z_stop}"),
    ]:
        fig.add_hline(y=level, line_dash="dot", line_color="#cccccc",
                      annotation_text=label, annotation_position="right",
                      row=3, col=1)

    fig.add_hrect(y0=-z_exit, y1=z_exit,
                  fillcolor="rgba(44,160,44,0.07)", line_width=0,
                  row=3, col=1)

    for event, symbol, color in [
        ("long_spread",  "triangle-up",   _BLUE),
        ("short_spread", "triangle-down", _ORANGE),
        ("exit",         "circle",        _GREEN),
        ("stop",         "x",             _RED),
    ]:
        mask = signals_df["signal"] == event
        if mask.any():
            fig.add_trace(go.Scatter(
                x=signals_df.index[mask], y=z[mask],
                mode="markers", name=event,
                marker=dict(symbol=symbol, color=color, size=10, line=dict(width=1, color="white")),
            ), row=3, col=1)

    fig.update_layout(
        title=dict(
            text=f"Pairs Trading Charts  —  {ticker_a} / {ticker_b}",
            font=dict(size=16),
        ),
        height=850,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#dddddd", borderwidth=1,
        ),
        margin=dict(l=60, r=100, t=80, b=40),
    )
    fig.update_yaxes(title_text="Rebased Price",      gridcolor="#f0f0f0", row=1, col=1)
    fig.update_yaxes(title_text="log(A) − β·log(B)",  gridcolor="#f0f0f0", row=2, col=1)
    fig.update_yaxes(title_text="Z-Score",             gridcolor="#f0f0f0", row=3, col=1)
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")

    return fig


def plot_all_dashboard(summary_df: pd.DataFrame) -> go.Figure:
    """Formatted summary table for all configured pairs."""
    n = len(summary_df)
    row_bg = [_ROW_A if i % 2 == 0 else _ROW_B for i in range(n)]
    stat_bg = ["#d4edda" if v == "yes" else "#f8d7da" for v in summary_df["stationary"]]

    col_labels = {
        "pair":          "Pair",
        "sector":        "Sector",
        "beta":          "Beta (β)",
        "adf_pval":      "ADF p-value",
        "stationary":    "Stationary",
        "half_life":     "Half-life (days)",
        "long_entries":  "Long Entries",
        "short_entries": "Short Entries",
        "exits":         "Exits",
        "stops":         "Stops",
        "stop_rate":     "Stop Rate",
    }
    cols    = [c for c in col_labels if c in summary_df.columns]
    headers = [col_labels[c] for c in cols]

    fill_colors = [stat_bg if c == "stationary" else row_bg for c in cols]
    font_colors = [
        ["#155724" if v == "yes" else "#721c24" for v in summary_df["stationary"]]
        if c == "stationary" else [_NORMAL_FG] * n
        for c in cols
    ]

    fig = go.Figure(data=[go.Table(
        columnwidth=[110, 155, 80, 100, 90, 130, 110, 120, 65, 65, 90],
        header=dict(
            values=[f"<b>{h}</b>" for h in headers],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=13),
            align="left",
            height=38,
        ),
        cells=dict(
            values=[summary_df[c].tolist() for c in cols],
            fill_color=fill_colors,
            align="left",
            font=dict(color=font_colors, size=12),
            height=32,
        ),
    )])

    fig.update_layout(
        title=dict(text="Pairs Trading  —  All Pairs Summary", font=dict(size=16)),
        height=max(280, 150 + n * 38),
        template="plotly_white",
        margin=dict(l=20, r=20, t=65, b=20),
    )
    return fig


# ── Interpretation helpers ────────────────────────────────────────────────────

def _rating(beta, adf, half_life, stop_rate_pct, total_trades):
    """Return (label, bg, fg) for the overall recommendation banner."""
    if adf["is_stationary"] and 5 <= half_life <= 40 and (total_trades == 0 or stop_rate_pct <= 0.20):
        return "RECOMMENDED", _GOOD_BG, _GOOD_FG
    if adf["is_stationary"]:
        return "CAUTION — Stationary but parameters need review", _WARN_BG, _WARN_FG
    if adf["p_value"] < 0.15:
        return "BORDERLINE — Try a shorter lookback period", _WARN_BG, _WARN_FG
    return "NOT RECOMMENDED — Insufficient evidence of cointegration", _BAD_BG, _BAD_FG


def _interp_beta(beta):
    if abs(beta) < 0.10:
        return ("bad",
                "Near zero — the regression found no meaningful linear relationship between "
                "the two stocks' log-prices. This usually means they moved in opposite "
                "directions over the lookback window. The pair may be structurally broken. "
                "Check the price chart for a clear divergence trend.")
    if 0.80 <= beta <= 1.20:
        return ("good",
                f"Close to 1.0 — both stocks move proportionally in log-space. "
                "Dollar-neutral positioning requires roughly equal share counts, adjusted "
                "slightly by β. This is the ideal range for a stable pair.")
    if beta > 1.20:
        return ("neutral",
                f"Greater than 1 — stock A is more volatile than B in log-space. "
                f"To be dollar-neutral, hold fewer shares of A relative to B "
                f"(roughly 1 share of A per {beta:.2f} shares of B).")
    return ("neutral",
            f"Less than 1 — stock B is more volatile than A in log-space. "
            "To be dollar-neutral, hold more shares of A relative to B.")


def _interp_adf(p_value):
    if p_value < 0.01:
        return ("good",
                f"p = {p_value:.4f} — Very strong evidence of stationarity. "
                "The spread almost certainly mean-reverts. This is a high-confidence "
                "pairs trading candidate.")
    if p_value < 0.05:
        return ("good",
                f"p = {p_value:.4f} — Stationary at the 5% significance level. "
                "We can reject the null hypothesis that the spread has a unit root. "
                "The mean-reversion assumption is statistically justified.")
    if p_value < 0.10:
        return ("warn",
                f"p = {p_value:.4f} — Borderline. Some evidence of stationarity but "
                "below the standard 95% confidence threshold. Trade with reduced size "
                "and tighter stops. Consider shortening the lookback period.")
    if p_value < 0.20:
        return ("warn",
                f"p = {p_value:.4f} — Weak evidence of stationarity. The spread shows "
                "some mean-reversion tendencies but we cannot confirm it statistically. "
                "Try a shorter period (e.g. 1y or 6mo) to find a more stable window.")
    return ("bad",
            f"p = {p_value:.4f} — Not stationary. The spread is likely trending or a "
            "random walk rather than mean-reverting. Running a pairs strategy on this "
            "pair as-is carries a high risk of the spread continuing to move against "
            "your position rather than reverting.")


def _interp_half_life(hl, window):
    ideal_lo, ideal_hi = hl * 2, hl * 3
    window_fit = ideal_lo <= window <= ideal_hi
    window_note = (
        f"Your rolling window of {window} days is well-matched."
        if window_fit else
        f"Your rolling window ({window} days) is outside the suggested range "
        f"({int(ideal_lo)}–{int(ideal_hi)} days) — consider adjusting."
    )
    if hl == float("inf") or hl > 200:
        return ("bad",
                "No meaningful mean-reversion detected. The spread behaves like a "
                "random walk — it has no tendency to return to a fixed level.")
    if hl < 5:
        return ("warn",
                f"{hl} days — very fast reversion. Daily bars may be too slow to "
                "capture the move before it closes. Consider intraday data for this pair.")
    if hl <= 20:
        return ("good",
                f"{hl} days (~{hl/5:.1f} weeks) — fast reversion. Trades are likely to "
                f"close within 1–3 weeks. Active swing trading territory. {window_note}")
    if hl <= 40:
        return ("good",
                f"{hl} days (~{hl/5:.1f} weeks) — ideal for swing trading. Expect to "
                f"hold positions for 2–6 weeks on average. {window_note}")
    if hl <= 90:
        return ("warn",
                f"{hl} days (~{hl/5:.1f} weeks) — slow reversion. Trades may take "
                f"1–3 months to close. Large adverse moves are possible while waiting. "
                f"{window_note}")
    return ("bad",
            f"{hl} days (~{hl/5:.1f} weeks) — very slow. The spread drifts for months "
            f"before reverting, making it impractical for swing trading. {window_note}")


def _interp_window(window, half_life):
    ideal_lo, ideal_hi = int(half_life * 2), int(half_life * 3)
    if half_life == float("inf"):
        return ("bad", "No half-life to calibrate against — window choice is arbitrary.")
    if window < ideal_lo:
        return ("warn",
                f"Window ({window} days) is shorter than recommended ({ideal_lo}–{ideal_hi} days). "
                "The rolling mean and std are noisy, which inflates signal frequency "
                "and produces more false entries.")
    if window > ideal_hi:
        return ("warn",
                f"Window ({window} days) is longer than recommended ({ideal_lo}–{ideal_hi} days). "
                "The z-score reacts slowly to divergences. Real opportunities may be "
                "missed or entered too late.")
    return ("good",
            f"Window ({window} days) falls within the recommended range ({ideal_lo}–{ideal_hi} days) "
            "based on this pair's half-life. The z-score is well-calibrated.")


def _interp_entry(z_entry):
    if z_entry < 1.5:
        return ("warn",
                f"±{z_entry}σ — aggressive. Entries trigger frequently but at relatively "
                "modest deviations. Expect more trades, more noise, and lower per-trade "
                "profitability. Under a normal distribution, ±1.5σ occurs ~13% of the time.")
    if z_entry <= 2.0:
        return ("good",
                f"±{z_entry}σ — standard. Entries trigger only at statistically unusual "
                "deviations (~5% of the time under normality). Good balance between "
                "trade frequency and signal quality.")
    if z_entry <= 2.5:
        return ("good",
                f"±{z_entry}σ — conservative. Fewer trades, but each one represents a "
                "stronger-than-average divergence. Typically higher per-trade profit "
                "potential but longer waits between opportunities.")
    return ("warn",
            f"±{z_entry}σ — very wide. Entries will be rare. On shorter datasets "
            "you may see only 1–2 trades, making it hard to assess strategy performance.")


def _interp_exit(z_exit):
    if z_exit >= 1.0:
        return ("warn",
                f"±{z_exit}σ — early exit. You're closing before the spread fully "
                "reverts to its mean. This captures less of the available move per trade "
                "but reduces the risk of a reversal while in position.")
    if z_exit <= 0.25:
        return ("warn",
                f"±{z_exit}σ — patient exit. You're waiting for near-complete reversion. "
                "This maximises the captured move but risks the spread overshooting and "
                "reversing before you exit.")
    return ("good",
            f"±{z_exit}σ — balanced. Exits when the spread is close to its mean without "
            "waiting for a perfect zero crossing. Standard practice for mean-reversion strategies.")


def _interp_stop(z_stop, z_entry):
    gap = z_stop - z_entry
    if gap < 0.5:
        return ("warn",
                f"±{z_stop}σ — very tight stop, only {gap:.1f}σ beyond the entry. "
                "Small noise moves could trigger stops before the trade has any room "
                "to develop. Consider widening to at least entry + 1.0σ.")
    if gap <= 1.5:
        return ("good",
                f"±{z_stop}σ — {gap:.1f}σ beyond the entry threshold. "
                "Gives trades room to breathe while still capping losses if the spread "
                "keeps trending against the position.")
    return ("warn",
            f"±{z_stop}σ — wide stop, {gap:.1f}σ beyond entry. "
            "You're accepting potentially large losses before exiting. "
            "Ensure position sizing accounts for the full entry-to-stop distance.")


def _interp_balance(long_entries, short_entries):
    total = long_entries + short_entries
    if total == 0:
        return ("warn", "No entries generated. The spread never crossed the entry threshold "
                "during this period. Try lowering z_entry or using a shorter rolling window.")
    ratio = max(long_entries, short_entries) / total
    if ratio > 0.75:
        dominant = "long" if long_entries > short_entries else "short"
        return ("warn",
                f"{ratio:.0%} of entries were on the {dominant} side. A large imbalance "
                "suggests the spread has a directional bias — it may be trending rather "
                "than mean-reverting symmetrically around a stable mean.")
    return ("good",
            f"{long_entries} long, {short_entries} short — reasonably balanced. "
            "Symmetric entry distribution is consistent with a truly mean-reverting spread.")


def _interp_stop_rate(stops, exits):
    total = stops + exits
    if total == 0:
        return ("neutral", "No completed trades yet — stop rate cannot be calculated.")
    rate = stops / total
    if rate == 0:
        return ("good",
                "0% — every completed trade exited profitably. No positions were stopped out. "
                "Excellent signal quality for this parameter set.")
    if rate <= 0.10:
        return ("good",
                f"{rate:.0%} — very low. The vast majority of trades reverted as expected. "
                "Strong signal quality.")
    if rate <= 0.20:
        return ("good",
                f"{rate:.0%} — healthy. Most trades are profitable exits. "
                "A small number of stop-outs is normal and expected in any strategy.")
    if rate <= 0.30:
        return ("warn",
                f"{rate:.0%} — elevated. Nearly 1 in 3 trades is hitting the stop rather "
                "than reverting. Consider widening the entry threshold (fewer but stronger "
                "signals) or checking whether the pair is still cointegrated.")
    return ("bad",
            f"{rate:.0%} — high. More than 1 in 3 trades is stopping out. The spread is "
            "trending persistently after entry more often than it reverts. This is a warning "
            "sign of a broken cointegration relationship or poorly calibrated parameters.")


def _interp_days_in_pos(pct):
    if pct < 0.10:
        return ("neutral",
                f"{pct:.0%} of days in a position. Very selective — the strategy spends "
                "most of its time flat, waiting for strong signals.")
    if pct <= 0.35:
        return ("good",
                f"{pct:.0%} of days in a position. Reasonable exposure — active enough "
                "to generate returns while remaining selective about entry quality.")
    if pct <= 0.60:
        return ("warn",
                f"{pct:.0%} of days in a position. Frequently in a trade. Higher "
                "exposure means more sensitivity to regime changes or spread breakdowns.")
    return ("warn",
            f"{pct:.0%} of days in a position — almost always in a trade. "
            "This level of exposure suggests the thresholds may be too permissive, "
            "or the spread is very volatile around its mean.")


# ── Interpretation figure ─────────────────────────────────────────────────────

def plot_pair_interpretation(
    ticker_a: str,
    ticker_b: str,
    period: str,
    beta: float,
    adf: dict,
    half_life: float,
    signals_df: pd.DataFrame,
    params: dict,
) -> go.Figure:
    """
    Three-column table: Metric | Value | Interpretation.
    Each interpretation is dynamically generated from the actual data values.
    """
    counts     = signals_df["signal"].value_counts().to_dict()
    exits      = counts.get("exit", 0)
    stops      = counts.get("stop", 0)
    total      = exits + stops
    stop_rate  = stops / total if total > 0 else 0.0
    pct_pos    = (signals_df["position"] != 0).mean()
    long_e     = counts.get("long_spread", 0)
    short_e    = counts.get("short_spread", 0)
    n_days     = len(signals_df)
    window     = params["rolling_window"]

    rating_label, rating_bg, rating_fg = _rating(beta, adf, half_life, stop_rate, total)

    interps = {
        "beta":         _interp_beta(beta),
        "adf":          _interp_adf(adf["p_value"]),
        "half_life":    _interp_half_life(half_life, window),
        "window":       _interp_window(window, half_life),
        "entry":        _interp_entry(params["z_entry"]),
        "exit":         _interp_exit(params["z_exit"]),
        "stop":         _interp_stop(params["z_stop"], params["z_entry"]),
        "balance":      _interp_balance(long_e, short_e),
        "stop_rate":    _interp_stop_rate(stops, exits),
        "days_in_pos":  _interp_days_in_pos(pct_pos),
    }

    _bg = {"good": _GOOD_BG, "warn": _WARN_BG, "bad": _BAD_BG, "neutral": _ROW_A}
    _fg = {"good": _GOOD_FG, "warn": _WARN_FG, "bad": _BAD_FG, "neutral": _NORMAL_FG}

    metrics, values, interp_texts = [], [], []
    bg_metric, bg_value, bg_interp = [], [], []
    fg_metric, fg_value, fg_interp = [], [], []

    _alt = [0]

    def section(title: str) -> None:
        metrics.append(f"  {title}")
        values.append("")
        interp_texts.append("")
        for lst in (bg_metric, bg_value, bg_interp):
            lst.append(_SECTION_BG)
        for lst in (fg_metric, fg_value, fg_interp):
            lst.append(_SECTION_FG)

    def row(metric: str, value: str, key: str) -> None:
        rating_key, text = interps[key]
        row_bg = _ROW_A if _alt[0] % 2 == 0 else _ROW_B
        _alt[0] += 1
        cell_bg = _bg[rating_key]
        cell_fg = _fg[rating_key]
        metrics.append(f"  {metric}")
        values.append(value)
        interp_texts.append(text)
        bg_metric.append(row_bg)
        bg_value.append(row_bg)
        bg_interp.append(cell_bg)
        fg_metric.append(_NORMAL_FG)
        fg_value.append(_NORMAL_FG)
        fg_interp.append(cell_fg)

    section("PAIR STATISTICS")
    row("Hedge Ratio (β)",  f"{beta:.4f}",                           "beta")
    row("ADF p-value",      f"{adf['p_value']}",                     "adf")
    row("Half-life",        f"{half_life} days (~{half_life/5:.1f} wks)", "half_life")

    section("SIGNAL PARAMETERS")
    row("Rolling Window",   f"{window} days",                        "window")
    row("Entry Threshold",  f"±{params['z_entry']} σ",               "entry")
    row("Exit Threshold",   f"±{params['z_exit']} σ",                "exit")
    row("Stop Threshold",   f"±{params['z_stop']} σ",                "stop")

    section("SIGNAL QUALITY")
    row("Entry Balance",    f"{long_e} long / {short_e} short",      "balance")
    row("Stop Rate",        f"{stop_rate:.0%}  ({stops}/{total})" if total > 0 else "n/a", "stop_rate")
    row("Days in Position", f"{pct_pos:.0%}",                        "days_in_pos")

    n = len(metrics)

    banner_metric  = [f"  OVERALL ASSESSMENT"] + metrics
    banner_value   = [""] + values
    banner_interp  = [rating_label] + interp_texts
    banner_bg_m    = [rating_bg] + bg_metric
    banner_bg_v    = [rating_bg] + bg_value
    banner_bg_i    = [rating_bg] + bg_interp
    banner_fg_m    = [rating_fg] + fg_metric
    banner_fg_v    = [rating_fg] + fg_value
    banner_fg_i    = [rating_fg] + fg_interp

    fig = go.Figure(data=[go.Table(
        columnwidth=[180, 160, 520],
        header=dict(
            values=[
                f"<b>{ticker_a} / {ticker_b}</b>",
                f"<b>{period}  ·  {n_days:,} days</b>",
                "<b>Interpretation</b>",
            ],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=13),
            align="left",
            height=40,
        ),
        cells=dict(
            values=[banner_metric, banner_value, banner_interp],
            fill_color=[banner_bg_m, banner_bg_v, banner_bg_i],
            align="left",
            font=dict(
                color=[banner_fg_m, banner_fg_v, banner_fg_i],
                size=12,
            ),
            height=30,
        ),
    )])

    fig.update_layout(
        title=dict(
            text=f"Interpretation  —  {ticker_a} / {ticker_b}",
            font=dict(size=16),
        ),
        height=max(480, 130 + (n + 1) * 30),
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


# ── Backtest visualizations ───────────────────────────────────────────────────

def plot_equity_curve(
    equity_curve,
    trades,
    ticker_a: str,
    ticker_b: str,
    starting_capital: float,
) -> go.Figure:
    """
    Two-panel figure: equity line + drawdown.
    Shaded bands show when capital was deployed (green = exited, red = stopped).
    """
    equity = equity_curve["equity"]
    drawdown = (equity / equity.cummax() - 1) * 100

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.70, 0.30],
        subplot_titles=["Equity Curve", "Drawdown (%)"],
        vertical_spacing=0.08,
    )

    fig.add_trace(go.Scatter(
        x=equity.index, y=equity,
        name="Equity", line=dict(color=_BLUE, width=2),
    ), row=1, col=1)
    fig.add_hline(
        y=starting_capital, line_dash="dash", line_color="#aaaaaa",
        annotation_text=f"Start (${starting_capital:,.0f})",
        annotation_position="right", row=1, col=1,
    )

    for _, t in trades.head(50).iterrows():
        color = "rgba(44,160,44,0.07)" if t["exit_type"] == "exit" else "rgba(214,39,40,0.07)"
        fig.add_vrect(
            x0=t["entry_date"], x1=t["exit_date"],
            fillcolor=color, line_width=0,
            row=1, col=1,
        )

    fig.add_trace(go.Scatter(
        x=drawdown.index, y=drawdown,
        name="Drawdown", fill="tozeroy",
        line=dict(color=_RED, width=1),
        fillcolor="rgba(214,39,40,0.3)",
        showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        title=dict(text=f"Backtest — {ticker_a} / {ticker_b}", font=dict(size=16)),
        height=600,
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=60, r=100, t=70, b=40),
    )
    fig.update_yaxes(title_text="Portfolio Value ($)", gridcolor="#f0f0f0", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)", gridcolor="#f0f0f0", row=2, col=1)
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")
    return fig


def plot_trade_pnl(trades, ticker_a: str, ticker_b: str) -> go.Figure:
    """
    Bar chart of per-trade returns ordered by entry date.
    Green = profitable exit, Red = stop or loss.
    """
    fig = go.Figure()

    if trades.empty:
        fig.add_annotation(
            text="No completed trades",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color="#888888"),
        )
    else:
        colors = [_GREEN if row["pnl"] > 0 else _RED for _, row in trades.iterrows()]
        fig.add_trace(go.Bar(
            x=trades["entry_date"],
            y=trades["pnl_pct"] * 100,
            marker_color=colors,
            name="Trade Return",
        ))
        fig.add_hline(y=0, line_color="#aaaaaa", line_width=1)

    fig.update_layout(
        title=dict(text=f"Per-Trade P&L — {ticker_a} / {ticker_b}", font=dict(size=16)),
        xaxis_title="Entry Date",
        yaxis_title="Return (%)",
        template="plotly_white",
        height=380,
        margin=dict(l=60, r=40, t=60, b=40),
        showlegend=False,
    )
    return fig


def plot_backtest_metrics(
    metrics: dict,
    trades,
    ticker_a: str,
    ticker_b: str,
    params: dict,
) -> go.Figure:
    """
    Styled metrics table matching the visual style of plot_pair_stats.
    Sections: PERFORMANCE and TRADE STATISTICS.
    """
    import math

    def _fmt_pct(v):
        return f"{v:.1%}" if not (isinstance(v, float) and math.isnan(v)) else "n/a"

    def _fmt_float(v, decimals=2):
        return f"{v:.{decimals}f}" if not (isinstance(v, float) and math.isnan(v)) else "n/a"

    def _fmt_dollar(v):
        return f"${v:,.0f}" if not (isinstance(v, float) and math.isnan(v)) else "n/a"

    metrics_list, values, bg_left, bg_right = [], [], [], []

    def section(title):
        metrics_list.append(f"  {title}")
        values.append("")
        bg_left.append(_SECTION_BG)
        bg_right.append(_SECTION_BG)

    _alt = [0]

    def row(label, value, highlight=None):
        bg = _ROW_A if _alt[0] % 2 == 0 else _ROW_B
        _alt[0] += 1
        metrics_list.append(f"  {label}")
        values.append(str(value))
        bg_left.append(bg)
        bg_right.append(
            _GOOD_BG if highlight == "good" else
            _WARN_BG if highlight == "warn" else
            _BAD_BG  if highlight == "bad"  else bg
        )

    section("PERFORMANCE")

    tr = metrics["total_return"]
    row("Total Return", _fmt_pct(tr),
        "good" if tr > 0 else "bad" if tr < 0 else None)

    cagr = metrics["cagr"]
    row("CAGR", _fmt_pct(cagr),
        "good" if cagr > 0.05 else "warn" if cagr >= 0 else "bad")

    sh = metrics["sharpe"]
    row("Sharpe Ratio", _fmt_float(sh),
        "good" if sh > 1.0 else "warn" if sh >= 0.5 else "bad")

    md = metrics["max_drawdown"]
    row("Max Drawdown", _fmt_pct(md),
        "good" if md > -0.10 else "warn" if md >= -0.25 else "bad")

    section("TRADE STATISTICS")

    row("Number of Trades", metrics["n_trades"])

    wr = metrics["win_rate"]
    row("Win Rate", _fmt_pct(wr),
        "good" if (not math.isnan(wr) and wr > 0.60)
        else "warn" if (not math.isnan(wr) and wr >= 0.40)
        else "bad" if not math.isnan(wr) else None)

    row("Avg Win",  _fmt_dollar(metrics["avg_win"]))
    row("Avg Loss", _fmt_dollar(metrics["avg_loss"]))

    pf = metrics["profit_factor"]
    pf_str = "∞" if pf == float("inf") else _fmt_float(pf)
    pf_hl = (
        "good" if pf == float("inf") or (not math.isnan(pf) and pf > 1.5)
        else "warn" if not math.isnan(pf) and pf >= 1.0
        else "bad" if not math.isnan(pf) else None
    )
    row("Profit Factor", pf_str, pf_hl)

    ahd = metrics["avg_hold_days"]
    row("Avg Hold Period", f"{ahd:.1f} days" if not math.isnan(ahd) else "n/a")

    n = len(metrics_list)
    is_section = [bg == _SECTION_BG for bg in bg_left]
    font_left  = [_SECTION_FG if s else _NORMAL_FG for s in is_section]
    font_right = [_SECTION_FG if s else _NORMAL_FG for s in is_section]

    period = params.get("period", "")

    fig = go.Figure(data=[go.Table(
        columnwidth=[220, 200],
        header=dict(
            values=[
                f"<b>{ticker_a} / {ticker_b}  —  Backtest Results</b>",
                f"<b>{period}  ·  {len(trades)} trades</b>",
            ],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=14),
            align="left",
            height=42,
        ),
        cells=dict(
            values=[metrics_list, values],
            fill_color=[bg_left, bg_right],
            align="left",
            font=dict(color=[font_left, font_right], size=12),
            height=28,
        ),
    )])

    fig.update_layout(
        title=dict(text=f"Backtest Metrics  —  {ticker_a} / {ticker_b}", font=dict(size=16)),
        height=max(400, 110 + n * 28),
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


def plot_backtest_interpretation(
    metrics: dict,
    trades,
    ticker_a: str,
    ticker_b: str,
    params: dict,
    half_life: float = None,
) -> go.Figure:
    """
    Three-column table: Metric | Value | Plain-English Explanation.
    Each explanation is written in context of the actual values — not generic definitions.
    """
    import math

    def _nan(v):
        return isinstance(v, float) and math.isnan(v)

    def _fmt_pct(v):
        return f"{v:.1%}" if not _nan(v) else "n/a"

    def _fmt_float(v, d=2):
        return f"{v:.{d}f}" if not _nan(v) else "n/a"

    def _fmt_dollar(v):
        return f"${v:,.0f}" if not _nan(v) else "n/a"

    # ── Interpretation helpers ────────────────────────────────────────────────

    def _interp_total_return(tr, period):
        period_label = {"1y": "1-year", "2y": "2-year", "6mo": "6-month"}.get(period, period)
        if _nan(tr):
            return ("neutral", "No trades were completed — no return to measure.")
        if tr > 0.15:
            return ("good",
                    f"{tr:.1%} over the {period_label} window. Solid absolute return for a "
                    "market-neutral strategy. Keep in mind this figure doesn't account for "
                    "transaction costs or capital tied up as margin.")
        if tr > 0:
            return ("warn",
                    f"{tr:.1%} over the {period_label} window. Positive but modest. For context, "
                    "a US money-market fund yields ~4–5% annually with zero risk — this strategy "
                    "needs to clear that bar to justify the complexity and drawdown risk.")
        if tr > -0.05:
            return ("warn",
                    f"{tr:.1%} — a small loss over {period_label}. The strategy was marginally "
                    "unprofitable. This could be within normal variation, especially if only a "
                    "few trades were generated. Try a shorter lookback period or different pair.")
        return ("bad",
                f"{tr:.1%} — a meaningful loss over {period_label}. The pair's spread did not "
                "behave as a mean-reverting series in this window. The most likely cause: the "
                "ADF test failed or the spread had a strong directional trend. Check the spread "
                "chart for a clear drift away from the mean.")

    def _interp_cagr(cagr):
        if _nan(cagr):
            return ("neutral", "Cannot compute CAGR — no trades completed.")
        if cagr > 0.12:
            return ("good",
                    f"{cagr:.1%} annualized. This beats the S&P 500's long-run average of ~10%. "
                    "A market-neutral strategy generating equity-like returns with lower market "
                    "exposure is genuinely valuable — but verify it holds on out-of-sample data.")
        if cagr > 0.05:
            return ("warn",
                    f"{cagr:.1%} annualized. Positive but below equity market returns. A pairs "
                    "strategy at this level makes sense only if it's truly uncorrelated with the "
                    "market — if it is, the diversification benefit compensates for the lower yield.")
        if cagr > 0:
            return ("warn",
                    f"{cagr:.1%} annualized — barely positive. After transaction costs and slippage "
                    "(not modeled here), this may be a losing strategy in practice. The risk-free "
                    "rate of ~4–5% is a more meaningful hurdle than zero.")
        return ("bad",
                f"{cagr:.1%} annualized — negative. The strategy destroyed capital at a compound "
                "rate. This is a clear signal to reconsider the pair, the parameter settings, "
                "or the lookback period before committing capital.")

    def _interp_sharpe(sh):
        if _nan(sh) or sh == 0.0:
            return ("neutral", "Sharpe ratio could not be computed — equity curve too short.")
        if sh > 2.0:
            return ("good",
                    f"{sh:.2f} — exceptional. A Sharpe above 2 is rare and likely reflects a "
                    "particularly favorable period for this pair. Verify it's not an artifact "
                    "of in-sample overfitting before trading it live.")
        if sh > 1.0:
            return ("good",
                    f"{sh:.2f} — strong. For reference, the S&P 500 has historically averaged "
                    "~0.5–0.8 Sharpe. A market-neutral strategy above 1.0 is considered very good. "
                    "This means each unit of daily volatility you're taking on is being rewarded.")
        if sh > 0.5:
            return ("warn",
                    f"{sh:.2f} — acceptable. The strategy earns more than half a unit of return "
                    "for every unit of risk. Comparable to a passive equity investment but without "
                    "the directional market exposure — a reasonable tradeoff if the correlation is low.")
        if sh > 0:
            return ("warn",
                    f"{sh:.2f} — weak. The strategy is marginally profitable on a risk-adjusted "
                    "basis but barely. Small changes in the backtest period could flip this negative. "
                    "Consider this inconclusive.")
        return ("bad",
                f"{sh:.2f} — negative. You are taking on daily volatility (risk) but the strategy "
                "is losing money overall. A negative Sharpe is worse than simply holding cash. "
                "The pair's mean-reversion was not strong enough over this period.")

    def _interp_drawdown(md):
        if _nan(md) or md == 0.0:
            return ("neutral", "No drawdown — either no trades or all trades were profitable.")
        md_abs = abs(md)
        if md_abs < 0.05:
            return ("good",
                    f"Peak-to-trough decline of {md_abs:.1%}. Very mild. The worst period in the "
                    "backtest would have felt like routine noise — easy to hold through psychologically.")
        if md_abs < 0.10:
            return ("good",
                    f"Peak-to-trough decline of {md_abs:.1%}. Manageable. Most traders can hold "
                    "through a drawdown of this size without panic. A key question is whether the "
                    "drawdown occurred during a single extended losing trade or across multiple trades.")
        if md_abs < 0.20:
            return ("warn",
                    f"Peak-to-trough decline of {md_abs:.1%}. Noticeable. If this were a live account, "
                    "this would be a psychologically challenging period. Drawdowns in this range are "
                    "often when discretionary traders abandon systematic strategies — right before recovery.")
        return ("bad",
                f"Peak-to-trough decline of {md_abs:.1%}. Severe for a market-neutral strategy. "
                "A drawdown this large suggests the spread moved strongly and persistently against "
                "open positions. Check whether a stop-loss was triggered or whether the position "
                "was held all the way through.")

    def _interp_win_rate(wr, avg_win, avg_loss):
        if _nan(wr):
            return ("neutral", "No completed trades — win rate cannot be calculated.")
        if _nan(avg_win) or _nan(avg_loss):
            return ("neutral", f"{wr:.0%} win rate, but not enough data to assess the risk/reward balance.")
        rr = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")
        breakeven_wr = 1 / (1 + rr)
        if wr >= 0.60:
            return ("good",
                    f"{wr:.0%} — strong. More than 3 in 5 trades closed profitably. "
                    f"With a win/loss ratio of {rr:.2f}x (avg win ${abs(avg_win):,.0f} vs "
                    f"avg loss ${abs(avg_loss):,.0f}), the breakeven win rate is {breakeven_wr:.0%} — "
                    "you're clearing it comfortably.")
        if wr >= 0.40:
            gain_factor = wr * abs(avg_win) / ((1 - wr) * abs(avg_loss))
            verdict = "profitable" if gain_factor >= 1 else "unprofitable"
            return ("warn" if gain_factor >= 1 else "bad",
                    f"{wr:.0%} win rate — roughly equal wins and losses. What matters more is the "
                    f"size of wins vs losses: avg win ${abs(avg_win):,.0f} vs avg loss ${abs(avg_loss):,.0f} "
                    f"(ratio {rr:.2f}x). Breakeven requires a {breakeven_wr:.0%} win rate — you are "
                    f"{'above' if gain_factor >= 1 else 'below'} that threshold, making the strategy {verdict}.")
        return ("bad",
                f"{wr:.0%} — fewer than 2 in 5 trades profitable. To be net-profitable with this "
                f"win rate, each winning trade would need to be at least {(1-wr)/wr:.1f}x the size "
                f"of each losing trade. Avg win ${abs(avg_win):,.0f} vs avg loss ${abs(avg_loss):,.0f} "
                f"(ratio {rr:.2f}x) — this requirement is {'met' if rr >= (1-wr)/wr else 'not met'}.")

    def _interp_profit_factor(pf):
        if _nan(pf):
            return ("neutral", "Cannot compute profit factor — no completed trades or no losses.")
        if pf == float("inf"):
            return ("good",
                    "∞ — every completed trade was profitable. No losing trades at all. "
                    "This is exceptional but also rare in practice. Verify there were enough "
                    "trades to make this statistically meaningful (10+ is a reasonable minimum).")
        if pf > 2.0:
            return ("good",
                    f"{pf:.2f} — for every $1 lost across all losing trades, the strategy made "
                    f"${pf:.2f} across all winners. A profit factor above 2.0 is considered very "
                    "strong for a systematic strategy.")
        if pf > 1.5:
            return ("good",
                    f"{pf:.2f} — solid. The strategy is making $1.50+ for every $1 it loses in "
                    "aggregate. This is the range where most professional systematic strategies operate.")
        if pf > 1.0:
            return ("warn",
                    f"{pf:.2f} — marginally profitable. The strategy makes slightly more than it "
                    "loses across all trades, but the margin is thin. After transaction costs "
                    "(commissions, slippage), this could easily turn negative.")
        return ("bad",
                f"{pf:.2f} — the strategy lost more in aggregate than it made. Every $1 of "
                f"winning trades was offset by ${1/pf:.2f} of losing trades. The mean-reversion "
                "signal wasn't strong enough to overcome the losing trades in this window.")

    def _interp_hold_days(ahd, hl):
        if _nan(ahd):
            return ("neutral", "No completed trades — average hold period cannot be calculated.")
        hl_note = (
            f" The pair's half-life is {hl} days, suggesting trades should typically "
            f"close in {hl:.0f}–{hl*2:.0f} days — the actual average of {ahd:.0f} days "
            f"{'is within' if hl <= ahd <= hl * 2 else 'falls outside'} this range."
        ) if hl and not math.isinf(hl) else ""
        if ahd < 5:
            return ("warn",
                    f"{ahd:.1f} days on average — very short. This is at the edge of what daily "
                    f"bars can reliably capture. Very short holds increase transaction cost drag.{hl_note}")
        if ahd <= 30:
            return ("good",
                    f"{ahd:.1f} days on average — typical swing trade duration. Short enough "
                    f"to keep capital working efficiently, long enough to avoid excessive friction.{hl_note}")
        if ahd <= 60:
            return ("warn",
                    f"{ahd:.1f} days on average — trades are taking 1–2 months to resolve. "
                    "Capital is tied up for extended periods, limiting the number of annual "
                    f"opportunities and increasing sensitivity to regime changes.{hl_note}")
        return ("warn",
                f"{ahd:.1f} days — very long holds. Capital is deployed for months at a time, "
                "which means a single spread breakdown can dominate the full-period results. "
                f"Consider a longer rolling window or wider entry threshold.{hl_note}")

    # ── Build overall rating ──────────────────────────────────────────────────
    tr  = metrics["total_return"]
    sh  = metrics["sharpe"]
    pf  = metrics["profit_factor"]

    if not _nan(tr) and tr > 0 and not _nan(sh) and sh > 1.0 and pf != float("nan") and pf > 1.5:
        rating_label = "PROFITABLE — Strong risk-adjusted performance"
        rating_bg, rating_fg = _GOOD_BG, _GOOD_FG
    elif not _nan(tr) and tr > 0:
        rating_label = "MARGINALLY PROFITABLE — Positive return but weak risk-adjusted metrics"
        rating_bg, rating_fg = _WARN_BG, _WARN_FG
    elif not _nan(tr) and tr > -0.03:
        rating_label = "BREAK-EVEN — Strategy was roughly flat over this period"
        rating_bg, rating_fg = _WARN_BG, _WARN_FG
    else:
        rating_label = "NOT PROFITABLE — Strategy lost money over this period"
        rating_bg, rating_fg = _BAD_BG, _BAD_FG

    # ── Per-row interpretations ───────────────────────────────────────────────
    period     = params.get("period", "2y")
    avg_win    = metrics["avg_win"]
    avg_loss   = metrics["avg_loss"]

    interps = {
        "total_return":  _interp_total_return(tr, period),
        "cagr":          _interp_cagr(metrics["cagr"]),
        "sharpe":        _interp_sharpe(sh),
        "max_drawdown":  _interp_drawdown(metrics["max_drawdown"]),
        "win_rate":      _interp_win_rate(metrics["win_rate"], avg_win, avg_loss),
        "profit_factor": _interp_profit_factor(pf),
        "avg_hold_days": _interp_hold_days(metrics["avg_hold_days"], half_life),
    }

    _bg = {"good": _GOOD_BG, "warn": _WARN_BG, "bad": _BAD_BG, "neutral": _ROW_A}
    _fg = {"good": _GOOD_FG, "warn": _WARN_FG, "bad": _BAD_FG, "neutral": _NORMAL_FG}

    metrics_col, values_col, interp_col = [], [], []
    bg_m, bg_v, bg_i = [], [], []
    fg_m, fg_v, fg_i = [], [], []

    _alt = [0]

    def section(title):
        metrics_col.append(f"  {title}")
        values_col.append("")
        interp_col.append("")
        for lst in (bg_m, bg_v, bg_i):
            lst.append(_SECTION_BG)
        for lst in (fg_m, fg_v, fg_i):
            lst.append(_SECTION_FG)

    def row(label, value, key):
        rating_key, text = interps[key]
        bg = _ROW_A if _alt[0] % 2 == 0 else _ROW_B
        _alt[0] += 1
        metrics_col.append(f"  {label}")
        values_col.append(value)
        interp_col.append(text)
        bg_m.append(bg)
        bg_v.append(bg)
        bg_i.append(_bg[rating_key])
        fg_m.append(_NORMAL_FG)
        fg_v.append(_NORMAL_FG)
        fg_i.append(_fg[rating_key])

    section("RETURNS")
    row("Total Return",   _fmt_pct(tr),                      "total_return")
    row("CAGR",          _fmt_pct(metrics["cagr"]),          "cagr")
    row("Sharpe Ratio",  _fmt_float(sh),                     "sharpe")
    row("Max Drawdown",  _fmt_pct(metrics["max_drawdown"]),  "max_drawdown")

    section("TRADE QUALITY")
    row("Win Rate",       _fmt_pct(metrics["win_rate"]),     "win_rate")
    row("Profit Factor",  _fmt_float(pf) if pf != float("inf") else "∞", "profit_factor")
    row("Avg Hold Period", f"{metrics['avg_hold_days']:.1f} days"
        if not _nan(metrics["avg_hold_days"]) else "n/a",    "avg_hold_days")

    n = len(metrics_col)

    # Prepend overall banner row
    banner_m = ["  OVERALL ASSESSMENT"] + metrics_col
    banner_v = [""] + values_col
    banner_i = [rating_label] + interp_col
    banner_bg_m = [rating_bg] + bg_m
    banner_bg_v = [rating_bg] + bg_v
    banner_bg_i = [rating_bg] + bg_i
    banner_fg_m = [rating_fg] + fg_m
    banner_fg_v = [rating_fg] + fg_v
    banner_fg_i = [rating_fg] + fg_i

    n_days = len(trades)

    fig = go.Figure(data=[go.Table(
        columnwidth=[160, 120, 560],
        header=dict(
            values=[
                f"<b>{ticker_a} / {ticker_b}</b>",
                f"<b>{period}  ·  {len(trades)} trades</b>",
                "<b>What This Means</b>",
            ],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=13),
            align="left",
            height=40,
        ),
        cells=dict(
            values=[banner_m, banner_v, banner_i],
            fill_color=[banner_bg_m, banner_bg_v, banner_bg_i],
            align="left",
            font=dict(color=[banner_fg_m, banner_fg_v, banner_fg_i], size=12),
            height=32,
        ),
    )])

    fig.update_layout(
        title=dict(text=f"Backtest Explanation  —  {ticker_a} / {ticker_b}", font=dict(size=16)),
        height=max(500, 130 + (n + 1) * 32),
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig

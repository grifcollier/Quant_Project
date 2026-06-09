"""Fama-French 5-factor analysis visualization."""

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analytics.fama_french import FACTOR_COLS
from src.viz.theme import (
    _BLUE, _GREEN, _RED, _ORANGE, _PURPLE,
    _HEADER_BG, _ROW_A, _ROW_B, _GOOD_BG, _WARN_BG, _BAD_BG,
)

_GRID    = "rgba(0,0,0,0.06)"
_TEXT    = "#2c3e50"
_SUBTEXT = "#7f8c8d"

_FACTOR_COLORS = {
    "Mkt-RF":          _BLUE,
    "SMB":             _ORANGE,
    "HML":             _GREEN,
    "RMW":             _PURPLE,
    "CMA":             "#8c564b",
    "Alpha":           "#e67e22",
    "Alpha (fitted)":  "#e67e22",
}


def _fmt(v, pct=False, dp=4):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    if pct:
        return f"{v:.2%}"
    return f"{v:.{dp}f}"


def _sig_stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def plot_ff5_analysis(
    result,
    rolling_betas: pd.DataFrame,
    annual_attr: pd.DataFrame,
    period: str,
    params: dict,
) -> go.Figure:
    """
    Three-panel Fama-French 5-factor figure.

    Row 1 (full width): Factor betas horizontal bar chart with ±1σ error bars.
    Row 2 left: Rolling 252-day factor loadings.  Row 2-3 right: Regression stats table.
    Row 3 left: Annual return attribution stacked bars.
    """
    fig = make_subplots(
        rows=3, cols=2,
        row_heights=[0.30, 0.42, 0.28],
        column_widths=[0.62, 0.38],
        shared_xaxes=False,
        specs=[
            [{"colspan": 2}, None],
            [{}, {"rowspan": 2, "type": "table"}],
            [{}, None],
        ],
        subplot_titles=[
            "Factor Betas  (Full-Period OLS)",
            "Rolling Factor Loadings  (252-day window)",
            "",
            "Annual Factor Attribution  (%)",
        ],
        vertical_spacing=0.17,
        horizontal_spacing=0.06,
    )

    # ── Row 1: Factor betas horizontal bar ───────────────────────────────────
    factor_labels = FACTOR_COLS + ["Alpha"]
    param_keys    = FACTOR_COLS + ["const"]
    betas  = [result.params[k] for k in param_keys]
    errors = [result.bse[k]    for k in param_keys]
    pvals  = [result.pvalues[k] for k in param_keys]
    colors = [_GREEN if b >= 0 else _RED for b in betas]

    # Encode the beta value and significance stars in the y-axis label so that
    # no floating text overlaps the error bar lines.
    y_labels = [
        f"{lbl}: {b:+.4f} {_sig_stars(p)}" if _sig_stars(p) else f"{lbl}: {b:+.4f}"
        for lbl, b, p in zip(factor_labels, betas, pvals)
    ]

    fig.add_trace(go.Bar(
        x=betas,
        y=y_labels,
        orientation="h",
        marker_color=colors,
        error_x=dict(type="data", array=errors, visible=True,
                     color=_SUBTEXT, thickness=1.5, width=6),
        showlegend=False,
        name="",
    ), row=1, col=1)
    fig.add_vline(x=0, line_dash="dash", line_color=_SUBTEXT, line_width=1, row=1, col=1)

    # ── Row 2 col 1: Rolling factor loadings ────────────────────────────────
    rb_valid = rolling_betas.dropna(how="all")
    for col_name in FACTOR_COLS + ["Alpha"]:
        if col_name not in rb_valid.columns:
            continue
        series = rb_valid[col_name].dropna()
        if series.empty:
            continue
        fig.add_trace(go.Scatter(
            x=series.index.tolist(),
            y=series.values.tolist(),
            mode="lines",
            name=col_name,
            line=dict(
                color=_FACTOR_COLORS[col_name],
                width=1.5,
                dash="dash" if col_name == "Alpha" else "solid",
            ),
        ), row=2, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color=_SUBTEXT, line_width=1, row=2, col=1)

    # ── Row 2-3 col 2: Regression stats table ───────────────────────────────
    rows_data = []
    all_bg    = []

    for i, (label, key) in enumerate(zip(factor_labels, param_keys)):
        b  = result.params[key]
        se = result.bse[key]
        t  = result.tvalues[key]
        p  = result.pvalues[key]
        rows_data.append((label, _fmt(b), _fmt(se), _fmt(t, dp=2), _fmt(p), _sig_stars(p)))
        all_bg.append(_ROW_A if i % 2 == 0 else _ROW_B)

    # Blank separator
    rows_data.append(("", "", "", "", "", ""))
    all_bg.append(_ROW_B)

    # Summary stats
    rows_data.append(("R²",       _fmt(result.rsquared,     dp=4), "", "", "", ""))
    all_bg.append(_ROW_A)
    rows_data.append(("Adj R²",   _fmt(result.rsquared_adj, dp=4), "", "", "", ""))
    all_bg.append(_ROW_B)

    alpha_ann = result.params["const"] * 252
    p_alpha   = result.pvalues["const"]
    rows_data.append(("α/yr", _fmt(alpha_ann, pct=True), "", "", "", ""))
    if p_alpha < 0.05 and alpha_ann > 0:
        all_bg.append(_GOOD_BG)
    elif p_alpha < 0.05 and alpha_ann < 0:
        all_bg.append(_BAD_BG)
    else:
        all_bg.append(_WARN_BG)

    rows_data.append(("N obs", str(int(result.nobs)), "", "", "", ""))
    all_bg.append(_ROW_A)

    fig.add_trace(go.Table(
        columnwidth=[2.2, 1.5, 1.3, 1.3, 1.3, 0.9],
        header=dict(
            values=["Factor", "β", "SE", "t-stat", "p-val", "Sig"],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=11, family="Inter, sans-serif"),
            align="left",
            height=28,
        ),
        cells=dict(
            values=[
                [r[0] for r in rows_data],
                [r[1] for r in rows_data],
                [r[2] for r in rows_data],
                [r[3] for r in rows_data],
                [r[4] for r in rows_data],
                [r[5] for r in rows_data],
            ],
            fill_color=[all_bg] * 6,
            font=dict(color=_TEXT, size=10, family="Inter, sans-serif"),
            align="left",
            height=24,
        ),
    ), row=2, col=2)

    # ── Row 3 col 1: Annual attribution stacked bars ─────────────────────────
    if not annual_attr.empty:
        year_labels = [str(y) for y in annual_attr.index.tolist()]
        for col_name in annual_attr.columns:
            vals = annual_attr[col_name].tolist()
            fig.add_trace(go.Bar(
                name=col_name,
                x=year_labels,
                y=[v * 100 for v in vals],
                marker_color=_FACTOR_COLORS.get(col_name, _SUBTEXT),
                showlegend=True,
                legend="legend2",
            ), row=3, col=1)

    # ── Layout ────────────────────────────────────────────────────────────────
    r2 = result.rsquared

    fig.update_layout(
        title=dict(
            text=(
                f"Fama-French 5-Factor Analysis — Combined Portfolio  |  {period}  |  "
                f"α = {alpha_ann:.2%}/yr  |  R² = {r2:.3f}"
            ),
            font=dict(size=15, color=_TEXT),
        ),
        height=950,
        template="plotly_white",
        hovermode="x unified",
        showlegend=True,
        barmode="relative",
        # Rolling loadings legend: horizontal strip centered in the gap between rows 2 and 3.
        # Gap is y=[0.207, 0.337]; midpoint ≈ 0.272.
        legend=dict(
            orientation="h",
            x=0.0, y=0.272,
            xanchor="left", yanchor="middle",
            font=dict(size=9),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="rgba(0,0,0,0.1)",
            borderwidth=1,
        ),
        # Attribution legend: to the right of col 1 (which ends at x≈0.583),
        # sitting in the table column area vertically aligned with row 3.
        legend2=dict(
            x=0.65, y=0.104,
            xanchor="left", yanchor="middle",
            font=dict(size=9),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="rgba(0,0,0,0.1)",
            borderwidth=1,
        ),
        margin=dict(l=80, r=40, t=70, b=40),
    )
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    fig.update_yaxes(gridcolor=_GRID)
    fig.update_xaxes(title_text="Beta", row=1, col=1)
    fig.update_yaxes(title_text="Loading", row=2, col=1)
    fig.update_yaxes(title_text="Contribution (%)", row=3, col=1)
    return fig

"""Combined multi-strategy portfolio visualization."""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.viz.theme import (
    _BLUE, _GREEN, _RED, _ORANGE, _PURPLE,
    _HEADER_BG, _ROW_A, _ROW_B,
    _GOOD_BG, _WARN_BG, _BAD_BG,
)

_GRID    = "rgba(0,0,0,0.06)"
_TEXT    = "#2c3e50"
_SUBTEXT = "#7f8c8d"

_STRATEGY_COLORS = {
    "CTA":    _BLUE,
    "PCA":    _GREEN,
    "Basket": _ORANGE,
    "Pairs":  _PURPLE,
}


def plot_portfolio_combined(
    combined_equity: pd.DataFrame,
    per_strategy_equity: dict,
    per_strategy_metrics: dict,
    combined_metrics: dict,
    weights_df: pd.DataFrame,
    params: dict,
) -> go.Figure:
    """
    Combined multi-strategy portfolio view.

    Layout:
      Row 1 col 1: Combined equity curve + drawdown
      Row 1 col 2: Metrics table (combined + per-strategy)
      Row 2 col 1: Per-strategy normalised equity (rebased to 1)
      Row 2 col 2: Average allocation weights stacked bar chart
    """
    equity   = combined_equity["equity"]
    drawdown = (equity / equity.cummax() - 1) * 100
    starting = float(equity.iloc[0])

    fig = make_subplots(
        rows=3, cols=2,
        row_heights=[0.38, 0.22, 0.40],
        column_widths=[0.60, 0.40],
        shared_xaxes=False,
        specs=[
            [{"rowspan": 1}, {"rowspan": 3, "type": "table"}],
            [{}             , None],
            [{}             , None],
        ],
        subplot_titles=["Combined Portfolio Equity", "", "Drawdown (%)", "Per-Strategy Returns (rebased)"],
        vertical_spacing=0.08,
    )

    # Combined equity
    fig.add_trace(go.Scatter(
        x=equity.index.tolist(), y=equity.values,
        mode="lines", name="Combined",
        line=dict(color=_BLUE, width=2.5),
    ), row=1, col=1)
    fig.add_hline(y=starting, line_dash="dash", line_color=_SUBTEXT, line_width=1, row=1, col=1)

    # Drawdown
    fig.add_trace(go.Scatter(
        x=drawdown.index.tolist(), y=drawdown.values,
        mode="lines", fill="tozeroy",
        line=dict(color=_RED, width=1),
        fillcolor="rgba(214,39,40,0.25)",
        name="Drawdown", showlegend=False,
    ), row=2, col=1)

    # Per-strategy normalised equity
    for name, eq_df in per_strategy_equity.items():
        eq = eq_df["equity"]
        norm = eq / float(eq.iloc[0])
        color = _STRATEGY_COLORS.get(name, _SUBTEXT)
        fig.add_trace(go.Scatter(
            x=eq.index.tolist(), y=norm.values,
            mode="lines", name=name,
            line=dict(color=color, width=1.5),
        ), row=3, col=1)
    fig.add_hline(y=1.0, line_dash="dot", line_color=_SUBTEXT, line_width=1, row=3, col=1)

    # Metrics table
    def _fmt(v, pct=False):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "n/a"
        return f"{v:.1%}" if pct else f"{v:.2f}"

    def _hl(v, hi, lo=None, invert=False):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return _ROW_A
        good = (v > hi) if not invert else (v < hi)
        warn = (v > lo) if lo is not None and not invert else (v < lo if lo else False)
        return _GOOD_BG if good else (_WARN_BG if warn else _BAD_BG)

    strategies = list(per_strategy_metrics.keys())
    col_labels  = ["Combined"] + strategies

    rows_spec = [
        ("Return",  lambda m: (_fmt(m.get("total_return"), pct=True),
                                _hl(m.get("total_return"), 0.10, 0))),
        ("CAGR",    lambda m: (_fmt(m.get("cagr"), pct=True),
                                _hl(m.get("cagr"), 0.08, 0))),
        ("Sharpe",  lambda m: (_fmt(m.get("sharpe")),
                                _hl(m.get("sharpe"), 1.0, 0.5))),
        ("Sortino", lambda m: (_fmt(m.get("sortino")),
                                _hl(m.get("sortino"), 1.5, 0.75))),
        ("Max DD",  lambda m: (_fmt(m.get("max_drawdown"), pct=True),
                                _hl(m.get("max_drawdown"), -0.10, -0.25, invert=True))),
        ("Calmar",  lambda m: (_fmt(m.get("calmar")),
                                _hl(m.get("calmar"), 1.0, 0.5))),
    ]

    all_metrics_ordered = [combined_metrics] + [per_strategy_metrics[s] for s in strategies]
    col_data = {"Metric": [r[0] for r in rows_spec]}
    col_bg   = {"Metric": [_ROW_A if i % 2 == 0 else _ROW_B for i in range(len(rows_spec))]}

    for label, m in zip(col_labels, all_metrics_ordered):
        vals, bgs = [], []
        for _, fn in rows_spec:
            v, bg = fn(m)
            vals.append(v)
            bgs.append(bg)
        col_data[label] = vals
        col_bg[label]   = bgs

    header_vals = list(col_data.keys())
    fig.add_trace(go.Table(
        header=dict(
            values=header_vals,
            fill_color=_HEADER_BG,
            font=dict(color="white", size=9, family="Inter, sans-serif"),
            align="left", height=24,
        ),
        cells=dict(
            values=[col_data[h] for h in header_vals],
            fill_color=[col_bg[h] for h in header_vals],
            font=dict(color=_TEXT, size=9, family="Inter, sans-serif"),
            align="left", height=22,
        ),
    ), row=1, col=2)

    period_label = params.get("period", "")
    strategies_label = " + ".join(col_labels[1:])

    fig.update_layout(
        title=dict(
            text=f"Multi-Strategy Portfolio  |  {strategies_label}  |  {period_label}",
            font=dict(size=16, color=_TEXT),
        ),
        height=780,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(
            x=0.01, y=0.22,
            xanchor="left", yanchor="top",
            font=dict(size=9),
            bgcolor="rgba(255,255,255,0.8)",
        ),
        margin=dict(l=60, r=30, t=70, b=40),
    )
    fig.update_yaxes(title_text="Portfolio Value ($)", gridcolor=_GRID, row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)",        gridcolor=_GRID, row=2, col=1)
    fig.update_yaxes(title_text="Normalised Return",   gridcolor=_GRID, row=3, col=1)
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    return fig

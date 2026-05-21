"""Visualizations for PCA statistical arbitrage."""

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.viz.theme import (
    _BLUE, _GREEN, _RED, _ORANGE,
    _HEADER_BG, _SECTION_BG, _ROW_A, _ROW_B,
    _GOOD_BG, _WARN_BG, _BAD_BG,
    _SECTION_FG, _NORMAL_FG, _GOOD_FG, _WARN_FG, _BAD_FG,
)

_GRID    = "rgba(0,0,0,0.06)"
_TEXT    = "#2c3e50"
_SUBTEXT = "#7f8c8d"
_AMBER   = "#e67e22"
_TEAL    = "#26a69a"


def plot_pca_equity(
    equity_curve: pd.DataFrame,
    metrics: dict,
    universe: str,
    params: dict,
) -> go.Figure:
    """Equity curve with drawdown panel and summary metrics table."""
    equity   = equity_curve["equity"]
    drawdown = (equity / equity.cummax() - 1) * 100
    starting = float(equity.iloc[0])

    fig = make_subplots(
        rows=2, cols=2,
        row_heights=[0.65, 0.35],
        column_widths=[0.60, 0.40],
        shared_xaxes=False,
        specs=[
            [{"rowspan": 1}, {"rowspan": 2, "type": "table"}],
            [{}             , None],
        ],
        subplot_titles=["Equity Curve", "", "Drawdown (%)"],
        vertical_spacing=0.10,
    )

    fig.add_trace(go.Scatter(
        x=equity.index, y=equity,
        mode="lines", name="Equity",
        line=dict(color=_BLUE, width=2),
    ), row=1, col=1)
    fig.add_hline(y=starting, line_dash="dash", line_color=_SUBTEXT,
                  annotation_text=f"Start (${starting:,.0f})",
                  annotation_position="right", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=drawdown.index, y=drawdown,
        mode="lines", fill="tozeroy",
        line=dict(color=_RED, width=1),
        fillcolor="rgba(214,39,40,0.25)",
        name="Drawdown", showlegend=False,
    ), row=2, col=1)

    def _fmt(v, pct=False):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "n/a"
        return f"{v:.1%}" if pct else f"{v:.2f}"

    def _hl(v, hi, lo=None, invert=False):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return _ROW_A
        good = v > hi if not invert else v < hi
        warn = (v > lo) if lo is not None and not invert else (v < lo if lo else False)
        return _GOOD_BG if good else (_WARN_BG if warn else _BAD_BG)

    perf_rows = [
        ("Total Return",  _fmt(metrics.get("total_return"), pct=True),
         _hl(metrics.get("total_return"), 0.05, 0)),
        ("CAGR",          _fmt(metrics.get("cagr"),         pct=True),
         _hl(metrics.get("cagr"),         0.05, 0)),
        ("Sharpe Ratio",  _fmt(metrics.get("sharpe")),
         _hl(metrics.get("sharpe"),       1.0,  0.5)),
        ("Sortino Ratio", _fmt(metrics.get("sortino")),
         _hl(metrics.get("sortino"),      1.5,  0.75)),
        ("Max Drawdown",  _fmt(metrics.get("max_drawdown"), pct=True),
         _hl(metrics.get("max_drawdown"), -0.10, -0.25, invert=True)),
        ("Calmar Ratio",  _fmt(metrics.get("calmar")),
         _hl(metrics.get("calmar"),       1.0,  0.5)),
    ]

    param_rows = [
        ("", ""),
        ("Universe",     universe),
        ("Period",       params.get("period", "")),
        ("Window",       f"{params.get('window', '')} bars"),
        ("Factors (k)",  str(params.get("n_factors", ""))),
        ("Top N / side", str(params.get("top_n", ""))),
        ("z-entry",      str(params.get("z_entry", ""))),
        ("z-exit",       str(params.get("z_exit", ""))),
        ("z-stop",       str(params.get("z_stop", ""))),
        ("Cost (bps)",   str(params.get("cost_bps", ""))),
    ]
    if params.get("test_period"):
        param_rows.append(("Test Period", params["test_period"]))

    all_rows  = perf_rows + [(r[0], r[1]) for r in param_rows]
    all_bg    = [r[2] for r in perf_rows] + [_ROW_A if i % 2 == 0 else _ROW_B
                                               for i in range(len(param_rows))]

    fig.add_trace(go.Table(
        header=dict(
            values=["Metric", "Value"],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=11, family="Inter, sans-serif"),
            align="left", height=28,
        ),
        cells=dict(
            values=[[r[0] for r in all_rows], [r[1] for r in all_rows]],
            fill_color=[all_bg, all_bg],
            font=dict(color=_TEXT, size=11, family="Inter, sans-serif"),
            align="left", height=25,
        ),
    ), row=1, col=2)

    fig.update_layout(
        title=dict(
            text=f"PCA Stat Arb -- {universe}  |  Equity & Performance",
            font=dict(size=16, color=_TEXT),
        ),
        height=620,
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=60, r=30, t=70, b=40),
    )
    fig.update_yaxes(title_text="Portfolio Value ($)", gridcolor=_GRID, row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)",        gridcolor=_GRID, row=2, col=1)
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    return fig


def plot_pca_zscore_heatmap(
    z_scores_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    universe: str,
    params: dict,
) -> go.Figure:
    """Heatmap of per-stock PCA residual z-scores over time (clipped to +/-4)."""
    z_clipped = z_scores_df.clip(-4, 4)

    fig = go.Figure(go.Heatmap(
        z=z_clipped.T.values,
        x=z_scores_df.index.tolist(),
        y=z_scores_df.columns.tolist(),
        colorscale=[
            [0.00, _RED],
            [0.35, "#f0f0f0"],
            [0.50, "#ffffff"],
            [0.65, "#f0f0f0"],
            [1.00, _GREEN],
        ],
        zmid=0, zmin=-4, zmax=4,
        colorbar=dict(title="z-score", tickfont=dict(color=_SUBTEXT, size=10)),
        hovertemplate="%{y}<br>%{x|%Y-%m-%d}<br>z = %{z:.2f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"PCA Residual Z-Scores -- {universe}",
            font=dict(size=16, color=_TEXT),
        ),
        height=max(300, 28 * len(z_scores_df.columns) + 130),
        template="plotly_white",
        margin=dict(l=80, r=80, t=70, b=50),
        xaxis=dict(gridcolor=_GRID),
        yaxis=dict(gridcolor=_GRID, tickfont=dict(size=10)),
    )
    return fig


def plot_pca_positions(
    positions_df: pd.DataFrame,
    universe: str,
) -> go.Figure:
    """Stacked bar chart showing active long/short positions over time."""
    n_long  = (positions_df == 1).sum(axis=1)
    n_short = (positions_df == -1).sum(axis=1)
    dates   = positions_df.index.tolist()

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("Long / Short Counts", "Net Position"),
        vertical_spacing=0.12,
        row_heights=[0.65, 0.35],
    )

    fig.add_trace(go.Bar(
        x=dates, y=n_long.values, name="Long",
        marker_color="rgba(44,160,44,0.7)",
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=dates, y=-n_short.values, name="Short",
        marker_color="rgba(214,39,40,0.7)",
    ), row=1, col=1)

    net = n_long - n_short
    fig.add_trace(go.Scatter(
        x=dates, y=net.values, mode="lines",
        line=dict(color=_AMBER, width=1.5), name="Net",
    ), row=2, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color=_SUBTEXT, line_width=1, row=2, col=1)

    fig.update_layout(
        title=dict(text=f"PCA Positions -- {universe}", font=dict(size=16, color=_TEXT)),
        height=480,
        template="plotly_white",
        barmode="overlay",
        margin=dict(l=60, r=30, t=70, b=40),
    )
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    fig.update_yaxes(gridcolor=_GRID)
    return fig


def plot_pca_walk_forward(
    stitched_equity: pd.DataFrame,
    fold_metrics: list,
    overall_metrics: dict,
    params: dict,
) -> go.Figure:
    """Walk-forward summary: stitched OOS equity, drawdown, per-fold Sharpe bars, metrics table."""
    equity   = stitched_equity["equity"]
    drawdown = (equity / equity.cummax() - 1) * 100
    starting = float(equity.iloc[0])

    fig = make_subplots(
        rows=3, cols=2,
        row_heights=[0.42, 0.22, 0.36],
        column_widths=[0.62, 0.38],
        shared_xaxes=False,
        specs=[
            [{"rowspan": 1}, {"rowspan": 3, "type": "table"}],
            [{}             , None],
            [{}             , None],
        ],
        subplot_titles=["Stitched OOS Equity", "", "Drawdown (%)", "Sharpe by Fold"],
        vertical_spacing=0.07,
    )

    fig.add_trace(go.Scatter(
        x=equity.index.tolist(), y=equity.values,
        mode="lines", name="OOS Equity",
        line=dict(color=_GREEN, width=2),
    ), row=1, col=1)
    fig.add_hline(y=starting, line_dash="dash", line_color=_SUBTEXT, line_width=1, row=1, col=1)

    for fm in fold_metrics[:-1]:
        fig.add_vline(x=fm["end"], line_dash="dot", line_color=_AMBER, line_width=1.2, row=1, col=1)

    fig.add_trace(go.Scatter(
        x=drawdown.index.tolist(), y=drawdown.values,
        mode="lines", fill="tozeroy",
        line=dict(color=_RED, width=1),
        fillcolor="rgba(214,39,40,0.25)",
        name="Drawdown", showlegend=False,
    ), row=2, col=1)

    fold_xlabels = [f"F{fm['fold']} {fm['start'].strftime('%b%y')}" for fm in fold_metrics]
    fold_sharpes = [float(fm.get("sharpe", 0)) for fm in fold_metrics]
    bar_colors   = [_GREEN if s > 1.0 else (_AMBER if s > 0 else _RED) for s in fold_sharpes]

    fig.add_trace(go.Bar(
        x=fold_xlabels, y=fold_sharpes,
        marker_color=bar_colors, showlegend=False,
        text=[f"{s:.2f}" for s in fold_sharpes],
        textposition="outside",
    ), row=3, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color=_SUBTEXT, line_width=1, row=3, col=1)

    all_metrics = [overall_metrics] + fold_metrics
    col_labels  = ["Overall"] + [f"F{fm['fold']}" for fm in fold_metrics]

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

    rows_spec = [
        ("Period",  lambda m: (
            (f"{m['start'].strftime('%b%y')}-{m['end'].strftime('%b%y')}"
             if "start" in m else "--"), _ROW_A)),
        ("Return",  lambda m: (_fmt(m.get("total_return"), pct=True),
                                _hl(m.get("total_return"), 0.05, 0))),
        ("Sharpe",  lambda m: (_fmt(m.get("sharpe")),
                                _hl(m.get("sharpe"), 1.0, 0.5))),
        ("Sortino", lambda m: (_fmt(m.get("sortino")),
                                _hl(m.get("sortino"), 1.5, 0.75))),
        ("Max DD",  lambda m: (_fmt(m.get("max_drawdown"), pct=True),
                                _hl(m.get("max_drawdown"), -0.10, -0.25, invert=True))),
    ]

    col_data = {"Metric": [r[0] for r in rows_spec]}
    col_bg   = {"Metric": [_ROW_A if i % 2 == 0 else _ROW_B for i in range(len(rows_spec))]}

    for label, m in zip(col_labels, all_metrics):
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

    n_folds      = len(fold_metrics)
    universe     = params.get("universe", "")
    period_label = params.get("period", "")

    fig.update_layout(
        title=dict(
            text=f"PCA Walk-Forward ({n_folds} folds × 1y)  |  {universe}  |  {period_label}",
            font=dict(size=16, color=_TEXT),
        ),
        height=740,
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=60, r=30, t=70, b=40),
    )
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    fig.update_yaxes(gridcolor=_GRID)
    return fig

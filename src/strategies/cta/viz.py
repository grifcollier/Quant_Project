"""Visualizations for the CTA trend-following strategy."""

import math

import numpy as np
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


def plot_cta_equity(
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
        ("Universe",    universe),
        ("Period",      params.get("period", "")),
        ("Instruments", str(params.get("n_instruments", ""))),
        ("Vol Target",  str(params.get("vol_target", ""))),
        ("Threshold",   str(params.get("threshold", ""))),
        ("Cost (bps)",  str(params.get("cost_bps", ""))),
    ]
    if params.get("test_period"):
        param_rows.append(("Test Period", params["test_period"]))

    all_rows = perf_rows + [(r[0], r[1]) for r in param_rows]
    all_bg   = [r[2] for r in perf_rows] + [
        _ROW_A if i % 2 == 0 else _ROW_B for i in range(len(param_rows))
    ]

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
            text=f"CTA Trend Following -- {universe}  |  Equity & Performance",
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


def plot_cta_signals(
    signals_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    universe: str,
) -> go.Figure:
    """
    Heatmap of combined EWMAC signal strength per instrument over time.

    Rows = instruments, columns = time. Colour = signal value (±2).
    """
    # Show signal, but mask bars with no active position (all-NaN) as white
    z = signals_df.T.values.astype(float)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=signals_df.index.tolist(),
        y=signals_df.columns.tolist(),
        colorscale=[
            [0.00, _RED],
            [0.35, "#f0f0f0"],
            [0.50, "#ffffff"],
            [0.65, "#f0f0f0"],
            [1.00, _GREEN],
        ],
        zmid=0, zmin=-2, zmax=2,
        colorbar=dict(
            title="EWMAC<br>signal",
            tickfont=dict(color=_SUBTEXT, size=10),
            tickvals=[-2, -1, 0, 1, 2],
        ),
        hovertemplate="%{y}<br>%{x|%Y-%m-%d}<br>signal = %{z:.3f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"CTA Signal Heatmap -- {universe}",
            font=dict(size=16, color=_TEXT),
        ),
        height=max(320, 28 * len(signals_df.columns) + 130),
        template="plotly_white",
        margin=dict(l=80, r=80, t=70, b=50),
        xaxis=dict(gridcolor=_GRID),
        yaxis=dict(gridcolor=_GRID, tickfont=dict(size=10)),
    )
    return fig


def plot_cta_contributions(
    equity_curve: pd.DataFrame,
    positions_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    universe: str,
    capital: float,
    weights_df: pd.DataFrame = None,
) -> go.Figure:
    """
    Bar chart of each instrument's total P&L contribution over the period.

    Computed as: weight[t-1,i] * daily_return[t,i], summed over all bars, × capital.
    Pass weights_df to use vol-targeted weights instead of equal-weight.
    """
    common = positions_df.index.intersection(prices_df.index)
    px  = prices_df.loc[common]

    if weights_df is not None:
        weights = weights_df.reindex(common).fillna(0.0)
    else:
        pos = positions_df.loc[common]
        n_active = pos.abs().sum(axis=1)
        weights  = pos.div(n_active.replace(0, np.nan), axis=0).fillna(0.0)

    daily_ret = px.pct_change().fillna(0.0)

    # Per-instrument cumulative contribution (fraction of capital)
    contrib = (weights.shift(1).fillna(0.0) * daily_ret).sum(axis=0) * capital
    contrib = contrib.sort_values()

    colors = [_GREEN if v >= 0 else _RED for v in contrib.values]

    fig = go.Figure(go.Bar(
        x=contrib.index.tolist(),
        y=contrib.values.tolist(),
        marker_color=colors,
        text=[f"${v:,.0f}" for v in contrib.values],
        textposition="outside",
        hovertemplate="%{x}<br>P&L: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_hline(y=0, line_color=_SUBTEXT, line_width=1)

    fig.update_layout(
        title=dict(
            text=f"CTA -- {universe}  |  P&L Contribution per Instrument",
            font=dict(size=16, color=_TEXT),
        ),
        height=480,
        template="plotly_white",
        showlegend=False,
        margin=dict(l=60, r=30, t=70, b=80),
        xaxis=dict(tickangle=-45, gridcolor=_GRID),
        yaxis=dict(title="P&L ($)", gridcolor=_GRID),
    )
    return fig


def plot_cta_sweep_heatmap(sweep_results: pd.DataFrame, metric: str = "sharpe_mean") -> go.Figure:
    """
    Grid-search result heatmap: threshold (x) × vol_span (y), one subplot per signal_mode.

    Shows three metrics side-by-side (sharpe_mean, cagr_mean, max_drawdown_mean)
    for each signal mode (binary / continuous).
    """
    metrics_spec = [
        ("sharpe_mean",        "Sharpe (mean)",   True),
        ("cagr_mean",          "CAGR (mean)",     True),
        ("max_drawdown_mean",  "Max DD (mean)",   False),
    ]

    signal_modes = list(sweep_results.index.get_level_values("signal_mode").unique())
    n_modes = len(signal_modes)
    n_metrics = len(metrics_spec)

    fig = make_subplots(
        rows=n_modes, cols=n_metrics,
        subplot_titles=[
            f"{mode.capitalize()} — {label}"
            for mode in signal_modes
            for _, label, _ in metrics_spec
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    for row_idx, mode in enumerate(signal_modes, start=1):
        mode_df = sweep_results.xs(mode, level="signal_mode")

        thresholds = sorted(mode_df.index.get_level_values("threshold").unique())
        vol_spans  = sorted(mode_df.index.get_level_values("vol_span").unique())

        for col_idx, (col_key, col_label, higher_is_better) in enumerate(metrics_spec, start=1):
            z = []
            for vs in vol_spans:
                row_vals = []
                for th in thresholds:
                    try:
                        v = float(mode_df.loc[(th, vs), col_key])
                    except KeyError:
                        v = float("nan")
                    row_vals.append(v)
                z.append(row_vals)

            if higher_is_better:
                colorscale = [[0.0, _RED], [0.5, "#f7f7f7"], [1.0, _GREEN]]
            else:
                # For drawdown: less negative is better → green = closer to 0
                colorscale = [[0.0, _GREEN], [0.5, "#f7f7f7"], [1.0, _RED]]

            z_flat = [v for row in z for v in row if not math.isnan(v)]
            zmid = 0.0 if z_flat and min(z_flat) < 0 < max(z_flat) else None

            text_labels = [
                [f"{v:.2f}" if not math.isnan(v) else "" for v in row]
                for row in z
            ]

            fig.add_trace(go.Heatmap(
                z=z,
                x=[str(th) for th in thresholds],
                y=[str(vs) for vs in vol_spans],
                colorscale=colorscale,
                zmid=zmid,
                text=text_labels,
                texttemplate="%{text}",
                textfont=dict(size=9, color=_TEXT),
                showscale=False,
                hovertemplate=(
                    f"threshold=%{{x}}  vol_span=%{{y}}<br>"
                    f"{col_label}=%{{z:.3f}}<extra>{mode}</extra>"
                ),
            ), row=row_idx, col=col_idx)

    fig.update_layout(
        title=dict(
            text="CTA Parameter Sweep — Mean fold metrics (threshold × vol_span)",
            font=dict(size=16, color=_TEXT),
        ),
        height=320 * n_modes + 80,
        template="plotly_white",
        margin=dict(l=60, r=30, t=80, b=50),
    )
    fig.update_xaxes(title_text="threshold", tickfont=dict(size=9))
    fig.update_yaxes(title_text="vol_span",  tickfont=dict(size=9))
    return fig


def plot_cta_walk_forward(
    stitched_equity: pd.DataFrame,
    fold_metrics: list,
    overall_metrics: dict,
    params: dict,
) -> go.Figure:
    """
    Walk-forward summary: stitched OOS equity, drawdown, per-fold Sharpe bars, metrics table.
    """
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
        line=dict(color=_BLUE, width=2),
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
    period_label = params.get("period", "")
    universe     = params.get("universe", "")
    mode_label   = params.get("signal_mode", "binary")

    fig.update_layout(
        title=dict(
            text=(f"CTA Walk-Forward ({n_folds} folds × 1y)  |  {universe}  |  "
                  f"{period_label}  |  {mode_label} signals"),
            font=dict(size=16, color=_TEXT),
        ),
        height=740,
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=60, r=30, t=70, b=40),
    )
    fig.update_yaxes(title_text="Portfolio Value ($)", gridcolor=_GRID, row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)",        gridcolor=_GRID, row=2, col=1)
    fig.update_yaxes(title_text="Sharpe Ratio",        gridcolor=_GRID, row=3, col=1)
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    return fig

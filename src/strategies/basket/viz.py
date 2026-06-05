"""Basket / ETF arbitrage visualizations."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.viz.theme import _BLUE, _GREEN, _RED, _ORANGE

_GRID    = "rgba(0,0,0,0.06)"
_TEXT    = "#2c3e50"
_SUBTEXT = "#7f8c8d"
_AMBER   = "#e67e22"
_PURPLE  = "#9467bd"


def plot_basket_spread(
    spread: pd.Series,
    zscore: pd.Series,
    signals_df: pd.DataFrame,
    etf: str,
    stocks: list,
    params: dict,
    split_date=None,
) -> go.Figure:
    """
    Two-panel chart: basket spread (top) and z-score with signal markers (bottom).
    """
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=(f"Basket Spread  ({etf} vs weighted basket)", "Z-Score"),
        vertical_spacing=0.10,
        row_heights=[0.50, 0.50],
    )

    spread_clean = spread.dropna()
    z_clean      = zscore.dropna()

    fig.add_trace(go.Scatter(
        x=spread_clean.index.tolist(), y=spread_clean.values,
        mode="lines", line=dict(color=_BLUE, width=1.5), name="Spread",
    ), row=1, col=1)
    fig.add_hline(y=float(spread_clean.mean()), line_dash="dash",
                  line_color=_SUBTEXT, line_width=1, row=1, col=1)

    fig.add_trace(go.Scatter(
        x=z_clean.index.tolist(), y=z_clean.values,
        mode="lines", line=dict(color=_PURPLE, width=1.5), name="Z-Score",
    ), row=2, col=1)

    z_entry = params.get("z_entry", 2.0)
    z_exit  = params.get("z_exit", 0.5)
    z_stop  = params.get("z_stop", 3.0)

    for val, clr, dash in [
        ( z_entry, _GREEN,   "dash"),
        (-z_entry, _RED,     "dash"),
        ( z_stop,  _RED,     "dot"),
        (-z_stop,  _GREEN,   "dot"),
    ]:
        fig.add_hline(y=val, line_dash=dash, line_color=clr,
                      line_width=1, row=2, col=1)
    fig.add_hrect(y0=-z_exit, y1=z_exit, fillcolor="rgba(44,160,44,0.06)",
                  line_width=0, row=2, col=1)

    # Entry / exit markers on z-score panel
    entries = signals_df[signals_df["signal"].isin(["long_spread", "short_spread"])]
    exits   = signals_df[signals_df["signal"].isin(["exit", "stop"])]

    if not entries.empty:
        z_at_entry = zscore.reindex(entries.index)
        fig.add_trace(go.Scatter(
            x=entries.index.tolist(), y=z_at_entry.values,
            mode="markers",
            marker=dict(color=_GREEN, size=8, symbol="triangle-up"),
            name="Entry",
        ), row=2, col=1)

    if not exits.empty:
        z_at_exit = zscore.reindex(exits.index)
        fig.add_trace(go.Scatter(
            x=exits.index.tolist(), y=z_at_exit.values,
            mode="markers",
            marker=dict(color=_RED, size=8, symbol="triangle-down"),
            name="Exit",
        ), row=2, col=1)

    # Train / test boundary
    if split_date is not None:
        for r in (1, 2):
            fig.add_vline(x=split_date, line_dash="dash",
                          line_color=_AMBER, line_width=1.5, row=r, col=1)
        fig.add_vrect(
            x0=split_date, x1=spread.index[-1],
            fillcolor="rgba(230,126,34,0.06)", line_width=0,
            annotation_text="Test", annotation_position="top left",
            annotation_font=dict(color=_AMBER, size=10),
        )

    stocks_str = ", ".join(stocks[:5]) + ("..." if len(stocks) > 5 else "")
    fig.update_layout(
        title=dict(
            text=f"Basket Spread -- {etf} vs [{stocks_str}]",
            font=dict(size=16, color=_TEXT),
        ),
        height=580,
        template="plotly_white",
        hovermode="x unified",
        showlegend=True,
        margin=dict(l=60, r=40, t=70, b=40),
    )
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    fig.update_yaxes(gridcolor=_GRID)
    return fig


_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#e67e22",
    "#7f7f7f", "#4ecdc4",
]


def plot_basket_combined(
    combined_equity: pd.DataFrame,
    combined_metrics: dict,
    leg_names: list,
    params: dict,
) -> go.Figure:
    """
    Combined portfolio: equity curve, drawdown, and summary metrics table.
    Individual leg returns are shown separately in plot_basket_legs().
    """
    import math

    combined = combined_equity["equity"]
    drawdown = (combined / combined.cummax() - 1) * 100
    starting = float(combined.iloc[0])

    fig = make_subplots(
        rows=2, cols=2,
        row_heights=[0.65, 0.35],
        column_widths=[0.60, 0.40],
        shared_xaxes=False,
        specs=[
            [{"rowspan": 1}, {"rowspan": 2, "type": "table"}],
            [{}             , None],
        ],
        subplot_titles=["Combined Portfolio Equity", "", "Drawdown (%)"],
        vertical_spacing=0.10,
    )

    fig.add_trace(go.Scatter(
        x=combined.index.tolist(), y=combined.values,
        mode="lines", name="Combined",
        line=dict(color=_BLUE, width=2.5),
    ), row=1, col=1)
    fig.add_hline(y=starting, line_dash="dash", line_color=_SUBTEXT,
                  annotation_text=f"Start (${starting:,.0f})",
                  annotation_position="right", row=1, col=1)

    fig.add_trace(go.Scatter(
        x=drawdown.index.tolist(), y=drawdown.values,
        mode="lines", fill="tozeroy",
        line=dict(color=_RED, width=1),
        fillcolor="rgba(214,39,40,0.25)",
        name="Drawdown", showlegend=False,
    ), row=2, col=1)

    from src.viz.theme import _HEADER_BG, _ROW_A, _ROW_B, _GOOD_BG, _WARN_BG, _BAD_BG

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

    m = combined_metrics
    perf_rows = [
        ("Total Return", _fmt(m.get("total_return"), pct=True),
         _hl(m.get("total_return"), 0.05, 0)),
        ("CAGR",         _fmt(m.get("cagr"),         pct=True),
         _hl(m.get("cagr"),         0.05, 0)),
        ("Sharpe",       _fmt(m.get("sharpe")),
         _hl(m.get("sharpe"),       1.0,  0.5)),
        ("Sortino",      _fmt(m.get("sortino")),
         _hl(m.get("sortino"),      1.5,  0.75)),
        ("Max Drawdown", _fmt(m.get("max_drawdown"), pct=True),
         _hl(m.get("max_drawdown"), -0.10, -0.25, invert=True)),
        ("Calmar",       _fmt(m.get("calmar")),
         _hl(m.get("calmar"),       1.0,  0.5)),
        ("Trades",       str(m.get("n_trades", 0)), _ROW_A),
        ("Win Rate",     _fmt(m.get("win_rate"),    pct=True),
         _hl(m.get("win_rate"),     0.55, 0.45)),
    ]
    param_rows = [
        ("", ""),
        ("Legs",    ", ".join(leg_names[:6]) + ("..." if len(leg_names) > 6 else "")),
        ("Period",  params.get("period", "")),
        ("Window",  f"{params.get('window', '')} bars"),
        ("z-entry", str(params.get("z_entry", ""))),
        ("z-exit",  str(params.get("z_exit",  ""))),
        ("Cost",    f"{params.get('cost_bps', 5)}bps"),
    ]
    if params.get("test_period"):
        param_rows.append(("OOS Period", params["test_period"]))

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

    etfs_label   = " + ".join(leg_names[:5]) + ("..." if len(leg_names) > 5 else "")
    period_label = params.get("period", "")
    test_label   = f"  |  OOS: {params['test_period']}" if params.get("test_period") else ""
    cost_label   = f"  |  cost: {params.get('cost_bps', 5)}bps  z={params.get('z_entry', 1.5)}"

    fig.update_layout(
        title=dict(
            text=f"Combined Portfolio -- {etfs_label}  |  {period_label}{test_label}{cost_label}",
            font=dict(size=16, color=_TEXT),
        ),
        height=600,
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=60, r=30, t=70, b=40),
    )
    fig.update_yaxes(title_text="Portfolio Value ($)", gridcolor=_GRID, row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)",        gridcolor=_GRID, row=2, col=1)
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    return fig


def plot_basket_legs(
    leg_equities: dict,
    leg_metrics: dict,
    params: dict,
) -> go.Figure:
    """
    Per-ETF comparison: normalised return curves, sorted return/Sharpe bar chart,
    and a per-ETF metrics table.
    """
    import math

    labels    = list(leg_equities.keys())
    color_map = {lbl: _PALETTE[i % len(_PALETTE)] for i, lbl in enumerate(labels)}

    fig = make_subplots(
        rows=2, cols=2,
        row_heights=[0.58, 0.42],
        column_widths=[0.58, 0.42],
        shared_xaxes=False,
        specs=[
            [{"rowspan": 1}, {"rowspan": 2, "type": "table"}],
            [{}             , None],
        ],
        subplot_titles=["Individual ETF Return (%)", "", "Total Return & Sharpe by ETF"],
        vertical_spacing=0.12,
    )

    # Normalised equity curves (each starts at 0 %)
    for lbl, eq in leg_equities.items():
        s0  = float(eq["equity"].iloc[0])
        pct = (eq["equity"] / s0 - 1) * 100
        fig.add_trace(go.Scatter(
            x=pct.index.tolist(), y=pct.values,
            mode="lines", name=lbl,
            line=dict(color=color_map[lbl], width=1.5),
        ), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color=_SUBTEXT, line_width=1, row=1, col=1)

    # Return bar chart sorted descending, Sharpe as text label
    sorted_labels = sorted(labels,
                           key=lambda l: leg_metrics[l].get("total_return", 0),
                           reverse=True)
    bar_returns = [leg_metrics[l].get("total_return", 0) * 100 for l in sorted_labels]
    bar_sharpes = [leg_metrics[l].get("sharpe", 0)              for l in sorted_labels]

    fig.add_trace(go.Bar(
        x=sorted_labels,
        y=bar_returns,
        marker_color=[color_map[l] for l in sorted_labels],
        showlegend=False,
        text=[f"{r:.1f}%  SR {s:.1f}" for r, s in zip(bar_returns, bar_sharpes)],
        textposition="outside",
        textfont=dict(size=9),
    ), row=2, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color=_SUBTEXT, line_width=1, row=2, col=1)

    # Per-ETF metrics table (one row per ETF)
    from src.viz.theme import _HEADER_BG, _ROW_A, _ROW_B, _GOOD_BG, _WARN_BG, _BAD_BG

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

    t_labels   = []
    t_returns  = []
    t_sharpes  = []
    t_dds      = []
    t_trades   = []
    t_winrates = []
    row_bgs    = []

    for i, lbl in enumerate(labels):
        m = leg_metrics[lbl]
        t_labels.append(lbl)
        t_returns.append(_fmt(m.get("total_return"), pct=True))
        t_sharpes.append(_fmt(m.get("sharpe")))
        t_dds.append(_fmt(m.get("max_drawdown"), pct=True))
        t_trades.append(str(m.get("n_trades", 0)))
        t_winrates.append(_fmt(m.get("win_rate"), pct=True))
        row_bgs.append(_ROW_A if i % 2 == 0 else _ROW_B)

    fig.add_trace(go.Table(
        header=dict(
            values=["ETF", "Return", "Sharpe", "Max DD", "Trades", "Win %"],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=10, family="Inter, sans-serif"),
            align="left", height=26,
        ),
        cells=dict(
            values=[t_labels, t_returns, t_sharpes, t_dds, t_trades, t_winrates],
            fill_color=[row_bgs] * 6,
            font=dict(color=_TEXT, size=10, family="Inter, sans-serif"),
            align="left", height=22,
        ),
    ), row=1, col=2)

    etfs_label   = " + ".join(labels[:5]) + ("..." if len(labels) > 5 else "")
    period_label = params.get("period", "")
    test_label   = f"  |  OOS: {params['test_period']}" if params.get("test_period") else ""
    cost_label   = f"  |  z={params.get('z_entry', 1.5)}  cost: {params.get('cost_bps', 5)}bps"

    fig.update_layout(
        title=dict(
            text=f"Individual ETF Returns -- {etfs_label}  |  {period_label}{test_label}{cost_label}",
            font=dict(size=16, color=_TEXT),
        ),
        height=680,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(
            x=0.01, y=0.97,
            xanchor="left", yanchor="top",
            font=dict(size=8),
            bgcolor="rgba(255,255,255,0.75)",
            bordercolor="rgba(0,0,0,0.08)",
            borderwidth=1,
            tracegroupgap=1,
        ),
        margin=dict(l=60, r=30, t=70, b=50),
    )
    fig.update_yaxes(title_text="Return (%)", gridcolor=_GRID, row=1, col=1)
    fig.update_yaxes(title_text="Return (%)", gridcolor=_GRID, row=2, col=1)
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    return fig


def plot_walk_forward_results(
    stitched_equity: pd.DataFrame,
    fold_metrics: list,
    overall_metrics: dict,
    params: dict,
) -> go.Figure:
    """
    Walk-forward validation summary: stitched OOS equity curve with fold boundaries,
    drawdown panel, per-fold Sharpe bar chart, and a fold metrics table.
    """
    import math

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

    # Equity curve
    fig.add_trace(go.Scatter(
        x=equity.index.tolist(), y=equity.values,
        mode="lines", name="OOS Equity",
        line=dict(color=_BLUE, width=2),
    ), row=1, col=1)
    fig.add_hline(y=starting, line_dash="dash", line_color=_SUBTEXT, line_width=1, row=1, col=1)

    # Fold boundary lines
    for fm in fold_metrics[:-1]:
        fig.add_vline(x=fm["end"], line_dash="dot", line_color=_AMBER,
                      line_width=1.2, row=1, col=1)

    # Drawdown
    fig.add_trace(go.Scatter(
        x=drawdown.index.tolist(), y=drawdown.values,
        mode="lines", fill="tozeroy",
        line=dict(color=_RED, width=1),
        fillcolor="rgba(214,39,40,0.25)",
        name="Drawdown", showlegend=False,
    ), row=2, col=1)

    # Per-fold Sharpe bars
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

    # Metrics table: Overall | Fold 1 | Fold 2 | ...
    from src.viz.theme import _HEADER_BG, _ROW_A, _ROW_B, _GOOD_BG, _WARN_BG, _BAD_BG

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

    all_metrics = [overall_metrics] + fold_metrics
    col_labels  = ["Overall"] + [f"F{fm['fold']}" for fm in fold_metrics]

    rows_spec = [
        ("Period",   lambda m: (
            (f"{m['start'].strftime('%b%y')}-{m['end'].strftime('%b%y')}"
             if "start" in m else "--"), _ROW_A)),
        ("Return",   lambda m: (_fmt(m.get("total_return"), pct=True),
                                 _hl(m.get("total_return"), 0.05, 0))),
        ("Sharpe",   lambda m: (_fmt(m.get("sharpe")),
                                 _hl(m.get("sharpe"), 1.0, 0.5))),
        ("Sortino",  lambda m: (_fmt(m.get("sortino")),
                                 _hl(m.get("sortino"), 1.5, 0.75))),
        ("Max DD",   lambda m: (_fmt(m.get("max_drawdown"), pct=True),
                                 _hl(m.get("max_drawdown"), -0.10, -0.25, invert=True))),
        ("Trades",   lambda m: (str(int(m.get("n_trades", 0))), _ROW_A)),
        ("Win Rate", lambda m: (_fmt(m.get("win_rate"), pct=True),
                                 _hl(m.get("win_rate"), 0.55, 0.45))),
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
    cost_label   = f"z={params.get('z_entry', 1.5)}  cost={params.get('cost_bps', 5)}bps"

    fig.update_layout(
        title=dict(
            text=f"Walk-Forward Validation ({n_folds} folds x 1y)  |  {period_label}  |  {cost_label}",
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


def plot_monte_carlo(
    mc: dict,
    actual_metrics: dict,
    label: str,
    params: dict,
) -> go.Figure:
    """
    3-panel Monte Carlo bootstrap chart.

    Top-left  : Equity path fan (5/25/50/75/95th percentile bands + actual).
    Bottom-left: Sharpe and max-drawdown distribution histograms side by side.
    Right col  : Summary table (worst / median / best vs. actual).
    """
    import math
    import numpy as np
    from src.viz.theme import _HEADER_BG, _ROW_A, _ROW_B, _GOOD_BG, _WARN_BG, _BAD_BG

    paths     = mc["equity_paths"]        # shape (n_store, path_length)
    sharpes   = mc["sharpes"]
    drawdowns = mc["drawdowns"]
    returns   = mc["returns"]
    capital   = mc["capital"]
    n_sims    = mc["n_sims"]
    n_pts     = paths.shape[1]
    x_axis    = list(range(n_pts))

    pcts = [5, 25, 50, 75, 95]
    bands = {p: np.percentile(paths, p, axis=0) for p in pcts}

    fig = make_subplots(
        rows=2, cols=3,
        row_heights=[0.55, 0.45],
        column_widths=[0.38, 0.28, 0.34],
        specs=[
            [{"colspan": 2}, None, {"rowspan": 2, "type": "table"}],
            [{"colspan": 1}, {"colspan": 1}, None],
        ],
        subplot_titles=[
            f"Equity Path Fan  ({n_sims:,} simulations)", "",
            "Return Distribution", "Max Drawdown Distribution",
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.06,
    )

    # ── Equity fan ────────────────────────────────────────────────────────────
    fill_pairs = [(5, 25, "rgba(31,119,180,0.10)"),
                  (25, 75, "rgba(31,119,180,0.18)"),
                  (75, 95, "rgba(31,119,180,0.10)")]
    for lo, hi, color in fill_pairs:
        fig.add_trace(go.Scatter(
            x=x_axis + x_axis[::-1],
            y=list(bands[hi]) + list(bands[lo])[::-1],
            fill="toself", fillcolor=color,
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ), row=1, col=1)

    for p, dash, width in [(5, "dot", 1), (50, "solid", 1.5), (95, "dot", 1)]:
        fig.add_trace(go.Scatter(
            x=x_axis, y=bands[p],
            mode="lines", line=dict(color=_BLUE, width=width, dash=dash),
            name=f"p{p}", showlegend=(p == 50),
        ), row=1, col=1)

    # Actual equity reconstructed from capital + cumulative P&L
    # (we only have bootstrapped paths here; mark actual starting/ending points)
    actual_return = actual_metrics.get("total_return", 0.0)
    actual_end    = capital * (1 + actual_return)
    fig.add_trace(go.Scatter(
        x=[0, n_pts - 1], y=[capital, actual_end],
        mode="lines+markers",
        line=dict(color=_ORANGE, width=2.5),
        marker=dict(size=7, color=_ORANGE),
        name="Actual",
    ), row=1, col=1)
    fig.add_hline(y=capital, line_dash="dash", line_color=_SUBTEXT,
                  line_width=1, row=1, col=1)

    # ── Return histogram ──────────────────────────────────────────────────────
    actual_return_val = actual_metrics.get("total_return", 0.0)
    fig.add_trace(go.Histogram(
        x=returns * 100, nbinsx=60,
        marker_color=_BLUE, opacity=0.7,
        name="Return", showlegend=False,
    ), row=2, col=1)
    fig.add_vline(x=actual_return_val * 100, line_color=_ORANGE, line_width=2,
                  annotation_text=f"Actual {actual_return_val:.1%}",
                  annotation_position="top right",
                  annotation_font=dict(color=_ORANGE, size=10),
                  row=2, col=1)

    # ── Max DD histogram ──────────────────────────────────────────────────────
    actual_dd = actual_metrics.get("max_drawdown", 0.0)
    fig.add_trace(go.Histogram(
        x=drawdowns * 100, nbinsx=60,
        marker_color=_RED, opacity=0.7,
        name="Max DD", showlegend=False,
    ), row=2, col=2)
    fig.add_vline(x=actual_dd * 100, line_color=_ORANGE, line_width=2,
                  annotation_text=f"Actual {actual_dd:.1%}",
                  annotation_position="top left",
                  annotation_font=dict(color=_ORANGE, size=10),
                  row=2, col=2)

    # ── Summary table ─────────────────────────────────────────────────────────
    def _pct(arr, p):
        return float(np.percentile(arr, p))

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

    rows = [
        ("Return",
         _fmt(_pct(returns, 5),   pct=True), _fmt(_pct(returns, 50),   pct=True),
         _fmt(_pct(returns, 95),  pct=True), _fmt(actual_return, pct=True)),
        ("Max DD",
         _fmt(_pct(drawdowns, 5), pct=True), _fmt(_pct(drawdowns, 50), pct=True),
         _fmt(_pct(drawdowns, 95),pct=True), _fmt(actual_dd, pct=True)),
        ("", "", "", "", ""),
        ("Simulations", str(n_sims), "", "", ""),
        ("Period",   params.get("period", ""),    "", "", ""),
        ("z-entry",  str(params.get("z_entry", "")), "", "", ""),
    ]

    row_bgs = [
        _hl(actual_return, 0.05, 0),
        _hl(actual_dd, -0.10, -0.25, invert=True),
        _ROW_A, _ROW_A, _ROW_B, _ROW_A,
    ]

    fig.add_trace(go.Table(
        header=dict(
            values=["Metric", "5th pct", "Median", "95th pct", "Actual"],
            fill_color=_HEADER_BG,
            font=dict(color="white", size=10, family="Inter, sans-serif"),
            align="left", height=26,
        ),
        cells=dict(
            values=[
                [r[0] for r in rows],
                [r[1] for r in rows],
                [r[2] for r in rows],
                [r[3] for r in rows],
                [r[4] for r in rows],
            ],
            fill_color=[row_bgs] * 5,
            font=dict(color=_TEXT, size=10, family="Inter, sans-serif"),
            align="left", height=24,
        ),
    ), row=1, col=3)

    period_label = params.get("period", "")
    fig.update_layout(
        title=dict(
            text=f"Monte Carlo Bootstrap — {label}  |  {period_label}  |  {n_sims:,} simulations",
            font=dict(size=15, color=_TEXT),
        ),
        height=640,
        template="plotly_white",
        hovermode="x unified",
        showlegend=True,
        legend=dict(x=0.01, y=0.97, font=dict(size=9)),
        margin=dict(l=60, r=30, t=70, b=40),
    )
    fig.update_yaxes(title_text="Portfolio Value ($)", gridcolor=_GRID, row=1, col=1)
    fig.update_yaxes(title_text="Count", gridcolor=_GRID, row=2, col=1)
    fig.update_yaxes(title_text="Count", gridcolor=_GRID, row=2, col=2)
    fig.update_xaxes(title_text="Trade #",    gridcolor=_GRID, showgrid=True, row=1, col=1)
    fig.update_xaxes(title_text="Return (%)", gridcolor=_GRID, showgrid=True, row=2, col=1)
    fig.update_xaxes(title_text="Max DD (%)", gridcolor=_GRID, showgrid=True, row=2, col=2)
    return fig

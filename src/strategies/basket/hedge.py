"""
Beta-hedge overlay for the basket strategy (backtest-only, additive third leg).

This module is deliberately SEPARATE from the traded basket: the hedge-basket
membership and weights computed here NEVER influence which stocks the spread
strategy trades (that stays with ``_run_trade_basket`` / the OLS fit). The hedge
basket exists only to estimate the residual market beta of the spread position
and size a SPY-shares hedge against it.

Causality
---------
N-PORT membership uses ``filing_date <= t`` where ``filing_date`` is the SEC
*filingDate* (public submission date, from ``edgar._get_filings``), so there is
no look-ahead. Prices and betas are trailing as of ``t``.

Phase map (see plan): Phase 1 = membership + weights (this file, below).
Later phases (net_beta, sizing, static/dynamic, overlay) are appended here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.market_beta import compute_market_beta


# ---------------------------------------------------------------------------
# Phase 1 — hedge-basket membership + weights
# ---------------------------------------------------------------------------
def _daily_reference_holdings(
    holdings_history: pd.DataFrame,
    dates: pd.DatetimeIndex,
    pool_n: int,
) -> dict:
    """
    Map each trading day to the most-recent-on-or-before N-PORT filing's
    top-``pool_n`` ``{ticker: shares}``. Causal: uses ``filing_date <= t``.

    ``holdings_history`` must come from
    ``build_constituent_history(..., top_n>=pool_n, include_shares=True)`` and
    therefore carries ``constituents`` and ``shares`` columns.
    """
    if holdings_history.empty or "shares" not in holdings_history.columns:
        return {d: {} for d in dates}

    hh = holdings_history.sort_values("filing_date").reset_index(drop=True)
    fdates = hh["filing_date"].values.astype("datetime64[ns]")

    out: dict = {}
    for d in dates:
        idx = int(np.searchsorted(fdates, np.datetime64(d, "ns"), side="right")) - 1
        if idx < 0:
            out[d] = {}
            continue
        row = hh.iloc[idx]
        tickers = list(row["constituents"])[:pool_n]
        shares = list(row["shares"])[:pool_n]
        out[d] = {t: s for t, s in zip(tickers, shares)}
    return out


def hedge_membership(
    holdings_history: pd.DataFrame,
    prices: pd.DataFrame,
    hold_n: int = 5,
    pool_n: int = 10,
    x_pp: float = 0.3,
    n_days: int = 3,
) -> pd.DataFrame:
    """
    Daily hedge-basket membership with hysteresis.

    For each trading day ``t``::

        value_i     = shares_i(last filing <= t) * price_i(t)
        value_pct_i = 100 * value_i / sum_j value_j     (j over priced pool names)

    Names are ranked by ``value``. A *challenger* (highest-ranked name outside the
    current set) displaces the *weakest incumbent* (lowest-ranked name inside the
    current set) only if its ``value_pct`` lead over that incumbent is ``>= x_pp``
    for ``n_days`` consecutive trading days; otherwise yesterday's set is carried
    forward. Members that drop out of the pool (removed by a new filing, or missing
    a price) are replaced immediately, without hysteresis.

    Parameters
    ----------
    holdings_history : from ``build_constituent_history(..., include_shares=True)``.
    prices           : daily close prices, columns=tickers (superset of the pool),
                       index = trading days.
    hold_n           : hedge-basket size (default 5).
    pool_n           : candidate pool size (default 10 — the top-10 holdings).
    x_pp             : hysteresis threshold in value-percentage points (default 0.3).
    n_days           : consecutive days the lead must hold (default 3).

    Returns
    -------
    DataFrame indexed by trading day, column ``members`` : list[str] (<= hold_n).
    Days before the first valid filing / with too few priced names are omitted
    until a basket can first be formed, then carried forward.
    """
    dates = prices.index
    ref = _daily_reference_holdings(holdings_history, dates, pool_n)

    current: list | None = None
    pending = None  # (challenger, incumbent, consecutive_days)
    idx_out, members_out = [], []

    for d in dates:
        shares_map = ref.get(d, {})

        # Mark the pool to today's prices (names with a valid price only)
        vals = {}
        for tk, sh in shares_map.items():
            px = prices.at[d, tk] if tk in prices.columns else np.nan
            if pd.notna(px) and pd.notna(sh) and sh > 0:
                vals[tk] = sh * px

        if len(vals) < hold_n:
            # Cannot (re)form a basket today; carry forward if we already have one.
            if current is not None:
                idx_out.append(d)
                members_out.append(list(current))
            continue

        total = sum(vals.values())
        vpct = {tk: 100.0 * v / total for tk, v in vals.items()}
        ranked = sorted(vpct, key=vpct.get, reverse=True)

        if current is None:
            current = ranked[:hold_n]
            pending = None
            idx_out.append(d)
            members_out.append(list(current))
            continue

        # Forced replacement: members that left the priced pool
        survived = [m for m in current if m in vpct]
        if len(survived) < len(current):
            current = survived
            for tk in ranked:
                if tk not in current:
                    current.append(tk)
                if len(current) == hold_n:
                    break
            pending = None  # a forced change resets any pending hysteresis

        # Marginal challenger vs weakest incumbent
        non_members = [tk for tk in ranked if tk not in current]
        if non_members:
            challenger = non_members[0]
            incumbent = min(current, key=lambda m: vpct[m])
            gap = vpct[challenger] - vpct[incumbent]
            if gap >= x_pp:
                if pending and pending[0] == challenger and pending[1] == incumbent:
                    pending = (challenger, incumbent, pending[2] + 1)
                else:
                    pending = (challenger, incumbent, 1)
                if pending[2] >= n_days:
                    current = [challenger if m == incumbent else m for m in current]
                    pending = None
            else:
                pending = None

        idx_out.append(d)
        members_out.append(list(current))

    return pd.DataFrame(
        {"members": members_out},
        index=pd.DatetimeIndex(idx_out, name="date"),
    )


def hedge_weights(
    membership: pd.DataFrame,
    holdings_history: pd.DataFrame,
    prices: pd.DataFrame,
    pool_n: int = 10,
) -> pd.DataFrame:
    """
    Daily value weights within the hedge basket::

        w_i(t) = shares_i(last filing) * price_i(t)
                 / sum_{j in members(t)} shares_j * price_j(t)

    Returns a DataFrame indexed like ``membership`` with column ``weights`` :
    ``dict{ticker: weight}`` summing to 1.0 over that day's members (empty dict on
    a day where nothing could be priced).
    """
    ref = _daily_reference_holdings(holdings_history, membership.index, pool_n)
    weights_out = []
    for d, members in membership["members"].items():
        shares_map = ref.get(d, {})
        vals = {}
        for tk in members:
            sh = shares_map.get(tk, np.nan)
            px = prices.at[d, tk] if tk in prices.columns else np.nan
            if pd.notna(sh) and pd.notna(px) and sh > 0:
                vals[tk] = sh * px
        total = sum(vals.values())
        weights_out.append({tk: v / total for tk, v in vals.items()} if total > 0 else {})
    return pd.DataFrame({"weights": weights_out}, index=membership.index)


# ---------------------------------------------------------------------------
# Phase 2 — net_beta
# ---------------------------------------------------------------------------
def _beta_valid_from(price_series: pd.Series, window: int) -> pd.Timestamp | None:
    """
    First date at which ``price_series`` has ``window`` valid daily returns — i.e.
    the earliest date the rolling beta is a real estimate rather than the
    ``compute_market_beta`` warm-up default (1.0). Returns None if never reached.
    """
    valid = price_series.pct_change().notna().cumsum()
    reached = valid[valid >= window]
    return reached.index[0] if not reached.empty else None


def compute_net_beta(
    etf_prices: pd.Series,
    stock_prices: pd.DataFrame,
    spy_prices: pd.Series,
    membership: pd.DataFrame,
    weights: pd.DataFrame,
    window: int = 252,
) -> pd.DataFrame:
    """
    Daily ``net_beta = beta_ETF - Σ_i w_i · beta_i`` over the hedge basket.

    Uses ``compute_market_beta`` (252-day rolling, ``pct_change`` simple returns,
    vs SPY) for both the ETF and each hedge-basket stock — the same convention as
    the pairs path. Because ``compute_market_beta`` fills its warm-up with 1.0 and
    clips to >=0.1, we independently gate on genuine warm-up completion: a day is
    **hedged only if the ETF and every current hedge-basket member each have >=
    ``window`` valid returns as of that day**; otherwise ``net_beta`` is NaN and the
    caller treats the trade as unhedged that day.

    Sign convention: ``net_beta > 0`` ⇒ the spread's long-ETF/short-basket exposure
    is net long the market. (The hedge direction also depends on the trade's
    ``direction``; see ``hedge_shares``.)

    Returns
    -------
    DataFrame indexed like ``membership`` with columns:
        net_beta    : float (NaN where warm-up not satisfied)
        etf_beta    : float
        basket_beta : float (Σ w_i·beta_i)
        hedged      : bool
    """
    idx = membership.index

    etf_beta = compute_market_beta(etf_prices, spy_prices, window).reindex(idx)
    etf_valid = _beta_valid_from(etf_prices, window)

    pool = sorted({t for members in membership["members"] for t in members})
    stock_beta = {}
    valid_from = {}
    for tk in pool:
        if tk not in stock_prices.columns:
            continue
        s = stock_prices[tk].dropna()
        stock_beta[tk] = compute_market_beta(s, spy_prices, window).reindex(idx)
        valid_from[tk] = _beta_valid_from(s, window)

    net_beta, b_etf_col, b_bsk_col, hedged_col = [], [], [], []
    w_series = weights["weights"]
    for d, members in membership["members"].items():
        w = w_series.at[d]
        b_etf = etf_beta.at[d]

        warm_ok = (
            etf_valid is not None and d >= etf_valid
            and bool(members) and bool(w)
            and all(
                tk in valid_from and valid_from[tk] is not None and d >= valid_from[tk]
                and tk in stock_beta and pd.notna(stock_beta[tk].at[d])
                for tk in members
            )
            and pd.notna(b_etf)
        )

        if not warm_ok:
            net_beta.append(np.nan)
            b_etf_col.append(b_etf if pd.notna(b_etf) else np.nan)
            b_bsk_col.append(np.nan)
            hedged_col.append(False)
            continue

        b_basket = sum(w[tk] * stock_beta[tk].at[d] for tk in members)
        net_beta.append(b_etf - b_basket)
        b_etf_col.append(b_etf)
        b_bsk_col.append(b_basket)
        hedged_col.append(True)

    return pd.DataFrame(
        {
            "net_beta": net_beta,
            "etf_beta": b_etf_col,
            "basket_beta": b_bsk_col,
            "hedged": hedged_col,
        },
        index=idx,
    )


def compute_traded_net_beta(
    segments: list,
    etf_prices: pd.Series,
    traded_prices: dict,
    spy_prices: pd.Series,
    window: int = 60,
    beta_window: int = 252,
) -> pd.DataFrame:
    """
    net_beta from the ACTUAL traded OLS basket (alternative to the N-PORT proxy).

    The traded spread is ``log(ETF) - (a + Σ_i b_i·log(stock_i))`` with ``b_i`` the
    rolling OLS coefficients from ``fit_basket`` — so the spread's true market
    sensitivity is ``net_beta = beta_ETF - Σ_i b_i·beta_i`` using those RAW
    coefficients (not value weights; they need not sum to 1 and may be negative).
    For each day ``t`` the OLS is refit on the trailing ``window`` bars (matching
    ``rolling_basket_spread``), and 252-day market betas are used. Causal.

    Parameters mirror the traded path: ``segments`` are the ``(start, end, stocks)``
    tuples actually traded, ``traded_prices`` is ``{ticker: price Series}`` for those
    stocks. Same warm-up gate as ``compute_net_beta`` (>= ``beta_window`` returns for
    the ETF and every traded stock).

    Returns a DataFrame[net_beta, etf_beta, basket_beta, hedged] indexed by day.
    """
    from src.analytics.basket import fit_basket

    etf_beta_full = compute_market_beta(etf_prices, spy_prices, beta_window)
    etf_valid = _beta_valid_from(etf_prices, beta_window)

    all_stocks = sorted({s for _, _, stx in segments for s in stx})
    sbeta, svalid = {}, {}
    for s in all_stocks:
        if s in traded_prices:
            ser = traded_prices[s].dropna()
            sbeta[s] = compute_market_beta(ser, spy_prices, beta_window)
            svalid[s] = _beta_valid_from(ser, beta_window)

    idx_out, nb_out, be_out, bb_out, hedged_out = [], [], [], [], []
    for s_start, s_end, stx in segments:
        avail = [s for s in stx if s in traded_prices]
        if len(avail) < 2:
            continue
        cdf = pd.DataFrame({s: traded_prices[s] for s in avail}).dropna()
        ea  = etf_prices.reindex(cdf.index).dropna()
        cdf = cdf.reindex(ea.index)
        seg_days = ea.index[(ea.index >= s_start) & (ea.index <= s_end)]
        for t in seg_days:
            pos = ea.index.get_loc(t)
            if pos < window - 1:
                continue
            coefs, _, _ = fit_basket(ea.iloc[pos - window + 1:pos + 1],
                                     cdf.iloc[pos - window + 1:pos + 1])
            warm = (
                etf_valid is not None and t >= etf_valid
                and pd.notna(etf_beta_full.get(t, np.nan))
                and all(
                    s in svalid and svalid[s] is not None and t >= svalid[s]
                    and pd.notna(sbeta[s].get(t, np.nan))
                    for s in avail
                )
            )
            idx_out.append(t)
            if not warm:
                nb_out.append(np.nan)
                be_out.append(etf_beta_full.get(t, np.nan))
                bb_out.append(np.nan)
                hedged_out.append(False)
                continue
            b_etf = float(etf_beta_full.loc[t])
            b_basket = sum(coefs[i] * float(sbeta[s].loc[t]) for i, s in enumerate(avail))
            nb_out.append(b_etf - b_basket)
            be_out.append(b_etf)
            bb_out.append(b_basket)
            hedged_out.append(True)

    df = pd.DataFrame(
        {"net_beta": nb_out, "etf_beta": be_out, "basket_beta": bb_out, "hedged": hedged_out},
        index=pd.DatetimeIndex(idx_out, name="date"),
    )
    return df[~df.index.duplicated(keep="last")]


# ---------------------------------------------------------------------------
# Phases 3-5 — hedge sizing (shares), static/dynamic P&L, and the overlay
# ---------------------------------------------------------------------------
def hedge_shares(net_beta: float, direction: int, notional: float, spy_price: float) -> float:
    """
    Signed SPY share count for the beta hedge (Phase 3).

    ``hedge_shares = -direction * net_beta * notional / SPY``. Negative ⇒ short SPY,
    positive ⇒ long SPY. The sign depends on BOTH ``direction`` (trade side) and
    ``sign(net_beta)`` — there is no "long-ETF ⇒ short SPY" shortcut.
    """
    if not np.isfinite(net_beta) or spy_price <= 0:
        return 0.0
    return -direction * net_beta * notional / spy_price


def apply_beta_hedge(
    trades: pd.DataFrame,
    unhedged_equity: pd.DataFrame,
    spy_prices: pd.Series,
    net_beta_df: pd.DataFrame,
    capital: float,
    mode: str = "static",
    borrow_bps_annual: float = 30.0,
    rebalance_bps: float = 1.0,
) -> dict:
    """
    Overlay a SPY-shares beta hedge on an already-computed (unhedged) backtest
    (Phases 3-5). Pure overlay: ``run_basket_backtest`` and all spread/sizing logic
    are untouched; this reconstructs the open-position days from ``trades`` (same
    ``entry < d <= exit`` mask as the engine) and adds a daily hedge P&L series.

    The signed SPY position (in dollars, + = long SPY) held on day ``d`` is
    ``pos_d = -direction * net_beta_used * notional``, so hedge P&L =
    ``pos_d * r_SPY(d)`` cancels the spread's market P&L
    ``direction * net_beta * notional * r_SPY``.

    Modes
    -----
    static  : ``net_beta_used = net_beta`` frozen at each trade's entry (``β*``);
              constant for the trade's life. Only ``r_SPY`` varies. Costs: entry +
              exit only. If a trade's entry day is not warmed up (``hedged=False``),
              that whole trade is unhedged.
    dynamic : ``net_beta_used = net_beta(d)`` recomputed daily (0 on un-warmed days);
              position re-struck daily, rebalance cost on each day's |Δpos|.

    Costs
    -----
    rebalance_bps : round-trip bps; charged as ``rebalance_bps/2`` per side on the
                    traded change in |position| (entry ramp, daily deltas, exit unwind).
    borrow        : ``borrow_bps_annual`` /252 per day on |position| whenever short SPY.

    Returns
    -------
    dict with:
        hedged_equity    : DataFrame['equity'] = unhedged + cumulative net hedge P&L
        daily_hedge      : Series (net hedge P&L per day, on the equity index)
        trade_hedge_pnl  : np.ndarray (per-trade net hedge P&L, trade order)
        hedge_pct_arr    : np.ndarray (per-trade hedge P&L / capital) for plotting
        total_hedge_cost : float (borrow + rebalance across all trades)
        n_hedged_trades  : int
    """
    if trades.empty or unhedged_equity.empty:
        return {
            "hedged_equity": unhedged_equity, "daily_hedge": pd.Series(dtype=float),
            "trade_hedge_pnl": np.array([]), "hedge_pct_arr": np.array([]),
            "total_hedge_cost": 0.0, "n_hedged_trades": 0,
        }

    all_dates = unhedged_equity.index
    r_spy = spy_prices.pct_change().reindex(all_dates).fillna(0.0)
    nb = net_beta_df["net_beta"]
    hedged_flag = net_beta_df["hedged"]

    half_spread = (rebalance_bps / 2.0) / 10_000.0
    borrow_daily = (borrow_bps_annual / 10_000.0) / 252.0

    daily_hedge = pd.Series(0.0, index=all_dates)
    trade_hedge_pnl, hedge_pct_arr = [], []
    total_cost = 0.0
    n_hedged = 0

    for _, tr in trades.iterrows():
        entry, exit_ = tr["entry_date"], tr["exit_date"]
        direction, notional = int(tr["direction"]), float(tr["notional"])
        open_days = all_dates[(all_dates > entry) & (all_dates <= exit_)]
        if len(open_days) == 0:
            trade_hedge_pnl.append(0.0)
            hedge_pct_arr.append(0.0)
            continue

        # Frozen entry beta for static mode
        beta_star = np.nan
        if entry in net_beta_df.index and bool(hedged_flag.at[entry]):
            beta_star = float(nb.at[entry])

        this_pnl = 0.0
        prev_pos = 0.0
        trade_hedged = False

        for d in open_days:
            if mode == "static":
                nb_used = beta_star if np.isfinite(beta_star) else np.nan
            else:  # dynamic
                nb_used = float(nb.at[d]) if (d in nb.index and bool(hedged_flag.at[d])) else np.nan

            pos = -direction * nb_used * notional if np.isfinite(nb_used) else 0.0
            if pos != 0.0:
                trade_hedged = True

            # P&L for holding pos over day d
            pnl_d = pos * float(r_spy.at[d])
            # Rebalance cost on the traded change in position
            cost_d = half_spread * abs(pos - prev_pos)
            # Borrow only while short SPY
            borrow_d = borrow_daily * abs(pos) if pos < 0 else 0.0

            net_d = pnl_d - cost_d - borrow_d
            daily_hedge.at[d] += net_d
            this_pnl += net_d
            total_cost += cost_d + borrow_d
            prev_pos = pos

        # Unwind cost at exit (pos -> 0)
        if prev_pos != 0.0:
            unwind = half_spread * abs(prev_pos)
            daily_hedge.at[open_days[-1]] += -unwind
            this_pnl -= unwind
            total_cost += unwind

        if trade_hedged:
            n_hedged += 1
        trade_hedge_pnl.append(this_pnl)
        hedge_pct_arr.append(this_pnl / capital)

    hedged_equity = unhedged_equity.copy()
    hedged_equity["equity"] = unhedged_equity["equity"] + daily_hedge.cumsum()

    return {
        "hedged_equity": hedged_equity,
        "daily_hedge": daily_hedge,
        "trade_hedge_pnl": np.asarray(trade_hedge_pnl),
        "hedge_pct_arr": np.asarray(hedge_pct_arr),
        "total_hedge_cost": total_cost,
        "n_hedged_trades": n_hedged,
    }

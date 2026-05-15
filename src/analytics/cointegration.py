"""Pairwise cointegration tests, universe scanner, and cascade stability check."""

import itertools

import numpy as np
import pandas as pd

from src.analytics.stationarity import adf_test, compute_half_life
from src.strategies.pairs.spread import compute_hedge_ratio, compute_spread

# Approximate trading days per period string
_PERIOD_DAYS = {
    "3mo": 63, "6mo": 126, "1y": 252, "2y": 504, "5y": 1260, "10y": 2520,
}

# Sub-periods to test for each initial period
_CASCADE_MAP = {
    "10y": ["5y", "2y", "1y", "6mo"],
    "5y":  ["2y", "1y", "6mo", "3mo"],
    "2y":  ["1y", "6mo", "3mo"],
    "1y":  ["6mo", "3mo"],
    "6mo": ["3mo"],
}


def test_pair(series_a: pd.Series, series_b: pd.Series) -> dict:
    """
    Run a full cointegration test on a single pair.

    Returns a dict with: beta, adf_stat, p_value, is_stationary, half_life.
    Reuses existing spread and stationarity modules so the results are
    consistent with the main analysis pipeline.
    """
    beta   = compute_hedge_ratio(series_a, series_b)
    spread = compute_spread(series_a, series_b, beta)
    adf    = adf_test(spread)
    hl     = compute_half_life(spread)
    return {
        "beta":         beta,
        "adf_stat":     adf["adf_stat"],
        "p_value":      adf["p_value"],
        "is_stationary": adf["is_stationary"],
        "half_life":    hl,
    }


def _correlation_filter(
    available: list,
    prices: dict,
    min_correlation: float,
) -> tuple:
    """
    Return (candidate_pairs, n_total, corr_matrix) where candidate_pairs is the
    subset of all unique pairs whose absolute return correlation meets the threshold.

    Uses return correlation (pct_change) which is more stable than price correlation.
    """
    # Align all price series to common dates
    price_df = pd.DataFrame({t: prices[t] for t in available}).dropna()
    returns  = price_df.pct_change().dropna()
    corr     = returns.corr()

    all_pairs = list(itertools.combinations(available, 2))
    candidates = [
        (ta, tb) for ta, tb in all_pairs
        if not np.isnan(corr.loc[ta, tb]) and abs(corr.loc[ta, tb]) >= min_correlation
    ]
    return candidates, len(all_pairs), corr


def scan_universe(
    tickers: list,
    prices: dict,
    max_pvalue: float = 0.10,
    min_half_life: float = 5.0,
    max_half_life: float = 100.0,
    min_correlation: float = 0.80,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Scan a universe for cointegrated pairs and return a ranked results table.

    A correlation pre-filter (default |r| >= 0.80) eliminates uncorrelated pairs
    before the expensive OLS + ADF step, making large-universe scans practical.

    Parameters
    ----------
    tickers        : List of ticker symbols to test.
    prices         : Dict mapping ticker → pd.Series of closing prices.
    max_pvalue     : ADF p-value threshold for the 'passes' flag.
    min_half_life  : Minimum half-life in days for the 'passes' flag.
    max_half_life  : Maximum half-life in days for the 'passes' flag.
    min_correlation: Absolute return correlation threshold for pre-filter.
                     Set to 0.0 to disable and test all pairs.
    verbose        : Print progress lines (pair counts, skipped pairs).

    Returns
    -------
    DataFrame sorted by adf_pval ascending (best candidates first), with
    columns: pair, ticker_a, ticker_b, correlation, beta, adf_pval,
             is_stationary, half_life, passes.
    """
    available = [t for t in tickers if t in prices]

    if len(available) < 2:
        return pd.DataFrame(columns=[
            "pair", "ticker_a", "ticker_b", "correlation", "beta",
            "adf_pval", "is_stationary", "half_life", "passes",
        ])

    # ── Correlation pre-filter ────────────────────────────────────────────────
    candidate_pairs, n_total, corr_matrix = _correlation_filter(
        available, prices, min_correlation
    )
    n_skipped = n_total - len(candidate_pairs)
    if verbose:
        print(
            f"  Correlation filter (|r| >= {min_correlation}): "
            f"{len(candidate_pairs)}/{n_total} pairs pass "
            f"({n_skipped} skipped)"
        )

    # ── OLS + ADF on candidates ───────────────────────────────────────────────
    rows = []
    for i, (ta, tb) in enumerate(candidate_pairs):
        if verbose and len(candidate_pairs) > 20 and i % 50 == 0 and i > 0:
            print(f"  Testing pair {i}/{len(candidate_pairs)}...")

        sa = prices[ta]
        sb = prices[tb]
        combined = pd.concat([sa.rename("a"), sb.rename("b")], axis=1).dropna()
        if len(combined) < 60:
            continue
        try:
            result = test_pair(combined["a"], combined["b"])
        except Exception:
            continue

        hl = result["half_life"]
        passes = (
            result["p_value"] < max_pvalue
            and hl != float("inf")
            and min_half_life <= hl <= max_half_life
        )
        rows.append({
            "pair":          f"{ta}/{tb}",
            "ticker_a":      ta,
            "ticker_b":      tb,
            "correlation":   round(float(corr_matrix.loc[ta, tb]), 3),
            "beta":          round(result["beta"], 4),
            "adf_pval":      round(result["p_value"], 4),
            "is_stationary": result["is_stationary"],
            "half_life":     round(hl, 1) if hl != float("inf") else float("inf"),
            "passes":        passes,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "pair", "ticker_a", "ticker_b", "correlation", "beta",
            "adf_pval", "is_stationary", "half_life", "passes",
        ])

    df = pd.DataFrame(rows).sort_values("adf_pval").reset_index(drop=True)
    return df


def cascade_scan(
    passing_pairs: list,
    prices: dict,
    initial_period: str,
    max_pvalue: float = 0.10,
    min_half_life: float = 5.0,
    max_half_life: float = 100.0,
) -> dict:
    """
    Re-test cointegration on progressively shorter sub-periods for pairs that
    passed the initial scan. Slices the already-fetched price data — no extra
    network calls.

    Parameters
    ----------
    passing_pairs  : List of (ticker_a, ticker_b) tuples from the initial scan.
    prices         : Dict of {ticker: pd.Series} from the initial fetch.
    initial_period : The period string used for the initial scan (e.g. '2y').

    Returns
    -------
    Dict keyed by 'TICKER_A/TICKER_B', each value a dict keyed by period string
    containing: adf_pval, is_stationary, half_life, passes.
    """
    sub_periods = _CASCADE_MAP.get(initial_period, [])
    if not sub_periods or not passing_pairs:
        return {}

    results = {}

    for ta, tb in passing_pairs:
        pair_key = f"{ta}/{tb}"
        sa = prices[ta]
        sb = prices[tb]
        pair_results = {}

        for period in sub_periods:
            n_days = _PERIOD_DAYS.get(period, 0)
            if n_days == 0:
                continue
            sa_sub = sa.iloc[-n_days:]
            sb_sub = sb.iloc[-n_days:]
            combined = pd.concat(
                [sa_sub.rename("a"), sb_sub.rename("b")], axis=1
            ).dropna()
            if len(combined) < 30:
                continue
            try:
                result = test_pair(combined["a"], combined["b"])
            except Exception:
                continue

            hl = result["half_life"]
            passes = (
                result["p_value"] < max_pvalue
                and hl != float("inf")
                and min_half_life <= hl <= max_half_life
            )
            pair_results[period] = {
                "adf_pval":      round(result["p_value"], 4),
                "is_stationary": result["is_stationary"],
                "half_life":     round(hl, 1) if hl != float("inf") else float("inf"),
                "passes":        passes,
            }

        if pair_results:
            results[pair_key] = pair_results

    return results

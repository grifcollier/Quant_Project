"""Pairwise cointegration tests and universe scanner."""

import itertools

import numpy as np
import pandas as pd

from src.analytics.stationarity import adf_test, compute_half_life
from src.strategies.pairs.spread import compute_hedge_ratio, compute_spread


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

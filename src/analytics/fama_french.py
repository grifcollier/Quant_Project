"""Fama-French 5-factor analysis: data fetching, regression, and rolling exposures."""

import io
import zipfile
import urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

FACTOR_COLS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
_FF5_URL    = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
)
_CACHE_FILE = "ff5_daily.csv"
_ROOT       = Path(__file__).parents[2]


def fetch_ff5_factors(
    cache_dir: Path | None = None,
    max_age_days: int = 7,
) -> pd.DataFrame:
    """
    Download and cache Fama-French 5-factor daily data from Kenneth French's library.

    Returns DataFrame with DatetimeIndex and columns [Mkt-RF, SMB, HML, RMW, CMA, RF].
    All values in decimal form (divided by 100 from the source % format).
    Caches to data/cache/ff5_daily.csv; re-downloads if file is older than max_age_days.
    """
    cache_path = (cache_dir or _ROOT / "data" / "cache") / _CACHE_FILE

    if cache_path.exists():
        age_days = (datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)).days
        if age_days < max_age_days:
            return pd.read_csv(cache_path, index_col=0, parse_dates=True)

    print("  Fetching Fama-French 5-factor daily data from Kenneth French's library...")
    with urllib.request.urlopen(_FF5_URL, timeout=30) as resp:
        raw = resp.read()

    zf       = zipfile.ZipFile(io.BytesIO(raw))
    csv_name = next(n for n in zf.namelist() if n.upper().endswith(".CSV"))
    text     = zf.read(csv_name).decode("utf-8", errors="ignore")

    # Collect only rows where the first comma-delimited token is an 8-digit YYYYMMDD date.
    # The French CSV has a plaintext header, daily data rows, then an annual section.
    data_lines = []
    in_data    = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first = stripped.split(",")[0].strip()
        if first.isdigit() and len(first) == 8:
            in_data = True
            data_lines.append(stripped)
        elif in_data:
            break  # first non-date line after data started = annual section

    if not data_lines:
        raise ValueError(
            "Could not parse FF5 CSV — unexpected format from Kenneth French's site."
        )

    df = pd.read_csv(
        io.StringIO("\n".join(data_lines)),
        header=None,
        names=["date"] + FACTOR_COLS + ["RF"],
    )
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    df = df.set_index("date").sort_index()
    df = df / 100.0  # Convert from % to decimal

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path)
    return df


def align_returns(
    equity: pd.DataFrame,
    ff5: pd.DataFrame,
) -> tuple:
    """
    Align portfolio daily returns with FF5 factors on shared trading days.

    Returns (excess_returns, factors) both indexed to the inner join.
    excess_returns = daily portfolio return minus risk-free rate.
    """
    port_ret = equity["equity"].pct_change().dropna()
    shared   = port_ret.index.intersection(ff5.index)
    port_ret = port_ret.reindex(shared)
    ff5_     = ff5.reindex(shared)
    excess   = port_ret - ff5_["RF"]
    return excess, ff5_[FACTOR_COLS]


def run_ff5_regression(
    excess_returns: pd.Series,
    factors: pd.DataFrame,
) -> "sm.regression.linear_model.RegressionResultsWrapper":
    """Full-period OLS: excess_return ~ Mkt-RF + SMB + HML + RMW + CMA + const."""
    X = sm.add_constant(factors, has_constant="add")
    return sm.OLS(excess_returns, X).fit()


def rolling_ff5_loadings(
    excess_returns: pd.Series,
    factors: pd.DataFrame,
    window: int = 252,
) -> pd.DataFrame:
    """
    Rolling FF5 regression using an explicit numpy lstsq loop.

    At each bar t, fit on the preceding `window` bars and assign coefficients
    to bar t. Uses the same lookback pattern as rolling_basket_spread in basket.py.

    Returns DataFrame with same index as excess_returns,
    columns = FACTOR_COLS + ["Alpha"]. First (window-1) rows are NaN.
    """
    y    = excess_returns.values.astype(float)
    X    = factors.values.astype(float)
    n    = len(y)
    cols = FACTOR_COLS + ["Alpha"]
    out  = np.full((n, len(cols)), np.nan)

    for t in range(window - 1, n):
        X_w = np.column_stack([X[t - window + 1 : t + 1], np.ones(window)])
        y_w = y[t - window + 1 : t + 1]
        try:
            coef, _, _, _ = np.linalg.lstsq(X_w, y_w, rcond=None)
        except np.linalg.LinAlgError:
            continue
        out[t] = coef  # order: [Mkt-RF, SMB, HML, RMW, CMA, Alpha]

    return pd.DataFrame(out, index=excess_returns.index, columns=cols)


def annual_attribution(
    rolling_betas: pd.DataFrame,
    factors: pd.DataFrame,
) -> pd.DataFrame:
    """
    Decompose returns into annual factor contributions.

    Each cell = sum over the year of (beta_t × factor_return_t).
    Returns DataFrame indexed by year (int), columns = FACTOR_COLS + ["Alpha (fitted)"].
    """
    aligned         = factors.reindex(rolling_betas.index)
    factor_contribs = rolling_betas[FACTOR_COLS].multiply(aligned, axis=0)
    alpha_contrib   = rolling_betas["Alpha"].rename("Alpha (fitted)")
    combined        = pd.concat([factor_contribs, alpha_contrib], axis=1).dropna()
    annual          = combined.resample("YE").sum()
    annual.index    = annual.index.year
    return annual

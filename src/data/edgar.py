"""
EDGAR N-PORT constituent history fetcher.

Downloads quarterly ETF holdings from SEC N-PORT-P filings to enable
point-in-time constituent lookups — eliminates survivorship bias from
using today's index composition for historical backtests.

Rate limit: SEC fair-access policy allows 10 req/sec.  We use ~5/sec.
User-Agent: required by SEC — must identify the requester.
Cache: all filings written to .cache/edgar/ so repeat runs are instant.
"""

import json
import re
import time
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_USER_AGENT   = "quant-project research@example.com"
_SUB_BASE     = "https://data.sec.gov/submissions"
_ARC_BASE     = "https://www.sec.gov/Archives/edgar/data"
_TICKERS_URL  = "https://www.sec.gov/files/company_tickers.json"
_CACHE_DIR    = Path(__file__).parent.parent.parent / ".cache" / "edgar"
_MIN_INTERVAL = 0.22   # ~4.5 req/sec — comfortably under the 10/sec limit

_t_last: list[float] = [0.0]


# ---------------------------------------------------------------------------
# Known trust structures: ticker → (trust_cik, series_id)
#
# ETFs that are series of a shared trust don't appear in company_tickers.json
# under their fund ticker. We handle them with this hardcoded table.
# Series IDs are stable identifiers assigned by the SEC at fund registration.
# ---------------------------------------------------------------------------
_TRUST_ETF_MAP: dict[str, tuple[int, str]] = {
    # SELECT SECTOR SPDR TRUST (CIK 1064641) — discovered 2024-02
    "XLF":  (1064641, "S000006411"),  # Financial Select Sector SPDR Fund
    "XLE":  (1064641, "S000006410"),  # Energy Select Sector SPDR Fund
    "XLK":  (1064641, "S000006415"),  # Technology Select Sector SPDR Fund
    "XLV":  (1064641, "S000006412"),  # Health Care Select Sector SPDR Fund
    "XLI":  (1064641, "S000006413"),  # Industrial Select Sector SPDR Fund
    "XLY":  (1064641, "S000006408"),  # Consumer Discretionary Select Sector SPDR Fund
    "XLP":  (1064641, "S000006409"),  # Consumer Staples Select Sector SPDR Fund
    "XLB":  (1064641, "S000006414"),  # Materials Select Sector SPDR Fund
    "XLC":  (1064641, "S000062095"),  # Communication Services Select Sector SPDR Fund
    "XLRE": (1064641, "S000051152"),  # Real Estate Select Sector SPDR Fund
    "XLU":  (1064641, "S000006416"),  # Utilities Select Sector SPDR Fund
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _get(url: str, timeout: int = 30) -> requests.Response:
    """Rate-limited GET with required User-Agent."""
    wait = _MIN_INTERVAL - (time.monotonic() - _t_last[0])
    if wait > 0:
        time.sleep(wait)
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=timeout)
    _t_last[0] = time.monotonic()
    resp.raise_for_status()
    return resp


def _get_partial(url: str, n_bytes: int = 2000) -> str:
    """Range GET — returns first n_bytes as text. Used for quick XML header reads."""
    wait = _MIN_INTERVAL - (time.monotonic() - _t_last[0])
    if wait > 0:
        time.sleep(wait)
    headers = {"User-Agent": _USER_AGENT, "Range": f"bytes=0-{n_bytes - 1}"}
    resp = requests.get(url, headers=headers, timeout=30)
    _t_last[0] = time.monotonic()
    return resp.text


# ---------------------------------------------------------------------------
# CIK + series lookup
# ---------------------------------------------------------------------------
def _resolve(ticker: str) -> tuple[int, Optional[str]]:
    """
    Return (cik, series_id) for a ticker.

    series_id is None for ETFs/stocks that have their own dedicated CIK
    (most iShares, Invesco, Vanguard funds and all individual stocks).
    For trust-based ETFs (SPDR sector funds), series_id identifies which
    fund series within the trust to filter filings for.
    """
    key = ticker.upper()

    # Known trust-based ETFs
    if key in _TRUST_ETF_MAP:
        return _TRUST_ETF_MAP[key]

    # Direct CIK lookup
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = _CACHE_DIR / "cik_map.json"
    if cache.exists():
        cik_map: dict = json.loads(cache.read_text())
    else:
        data = _get(_TICKERS_URL).json()
        cik_map = {v["ticker"].upper(): str(v["cik_str"]) for v in data.values()}
        cache.write_text(json.dumps(cik_map))

    if key not in cik_map:
        raise ValueError(
            f"CIK not found for '{ticker}'. "
            "If this is a SPDR/iShares/Vanguard series ETF, it may need to be added "
            "to _TRUST_ETF_MAP in src/data/edgar.py."
        )
    return int(cik_map[key]), None


def get_cik(ticker: str) -> int:
    """Return the trust/fund CIK for a ticker (ignores series_id)."""
    cik, _ = _resolve(ticker)
    return cik


# ---------------------------------------------------------------------------
# N-PORT filing index
# ---------------------------------------------------------------------------
def _get_filings(cik: int, series_id: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch N-PORT-P filing metadata for a CIK.

    If series_id is given (trust-based ETF), filters to only filings
    belonging to that specific series by reading a partial XML header.

    Returns DataFrame[filing_date, accession, primary_doc], sorted ascending.
    """
    url  = f"{_SUB_BASE}/CIK{cik:010d}.json"
    data = _get(url).json()
    recent = data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs  = recent.get("accessionNumber", [])
    pdocs = recent.get("primaryDocument", [])

    # Strip XSLT wrapper prefix (e.g. "xslFormNPORT-P_X01/primary_doc.xml" → "primary_doc.xml")
    # The XSLT path returns an HTML rendering; the sibling "primary_doc.xml" is the raw data.
    def _strip_xsl(doc: str) -> str:
        parts = doc.split("/")
        return parts[-1] if parts[-1].endswith(".xml") else doc

    candidates = [
        {"filing_date": pd.Timestamp(d), "accession": a, "primary_doc": _strip_xsl(p)}
        for f, d, a, p in zip(forms, dates, accs, pdocs)
        if f in ("NPORT-P", "N-PORT-P", "N-PORT")
    ]

    if not candidates:
        return pd.DataFrame(columns=["filing_date", "accession", "primary_doc"])

    df = pd.DataFrame(candidates).sort_values("filing_date").reset_index(drop=True)

    # For trust-based ETFs, filter to the specific series by peeking at XML headers
    if series_id:
        df = _filter_by_series(cik, df, series_id)

    return df


_SERIES_RE = re.compile(r"<seriesId>([^<]+)</seriesId>")


def _filter_by_series(cik: int, filings: pd.DataFrame, series_id: str) -> pd.DataFrame:
    """
    Keep only filings that belong to the given series_id.

    Uses a disk-cached mapping of accession → series_id so that each filing
    is only fetched once. Only reads the first 2KB of each XML (range request).
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    series_cache_file = _CACHE_DIR / f"series_map_{cik}.json"

    series_map: dict[str, str] = {}
    if series_cache_file.exists():
        series_map = json.loads(series_cache_file.read_text())

    keep = []
    cache_dirty = False

    for _, row in filings.iterrows():
        acc = row["accession"]

        if acc not in series_map:
            # Range-read the XML header to find the series ID
            acc_nd   = acc.replace("-", "")
            xml_url  = f"{_ARC_BASE}/{cik}/{acc_nd}/primary_doc.xml"
            try:
                text   = _get_partial(xml_url, n_bytes=1500)
                m      = _SERIES_RE.search(text)
                series_map[acc] = m.group(1).strip() if m else ""
            except Exception:
                series_map[acc] = ""
            cache_dirty = True

        if series_map[acc] == series_id:
            keep.append(row)

    if cache_dirty:
        series_cache_file.write_text(json.dumps(series_map))

    return pd.DataFrame(keep).reset_index(drop=True) if keep else pd.DataFrame(
        columns=["filing_date", "accession", "primary_doc"]
    )


# ---------------------------------------------------------------------------
# N-PORT XML parser
# ---------------------------------------------------------------------------
_NS_RE = re.compile(r"\{[^}]+\}")


def _strip_ns(tag: str) -> str:
    return _NS_RE.sub("", tag)


def _parse_nport_xml(xml_text: str) -> list[dict]:
    """
    Parse one N-PORT XML filing and return equity holdings.

    Each entry: {ticker: str, cusip: str, name: str, pct_val: float}
    Only long equity positions (assetCat in EC/EF) are included.
    Ticker may be empty string if not present in the filing — callers
    that need tickers should run resolve_cusips() on the returned cusips.
    Sorted descending by pct_val (largest weight first).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    holdings = []
    for elem in root.iter():
        if _strip_ns(elem.tag) != "invstOrSec":
            continue

        fields: dict[str, str] = {}
        for child in elem.iter():
            tag = _strip_ns(child.tag)
            if child.text and child.text.strip():
                fields.setdefault(tag, child.text.strip())

        if fields.get("payoffProfile", "").lower() != "long":
            continue
        asset = fields.get("assetCat", "")
        if asset and asset not in ("EC", "EF", ""):
            continue

        cusip  = fields.get("cusip", "").strip()
        ticker = fields.get("ticker", "").upper()
        if ticker in ("N/A", "NONE"):
            ticker = ""

        # Need either a ticker or CUSIP to be useful
        if not ticker and not cusip:
            continue

        try:
            pct = float(fields.get("pctVal", 0))
        except ValueError:
            pct = 0.0

        holdings.append({
            "ticker":  ticker,
            "cusip":   cusip,
            "name":    fields.get("name", ""),
            "pct_val": pct,
        })

    holdings.sort(key=lambda x: x["pct_val"], reverse=True)
    return holdings


# ---------------------------------------------------------------------------
# CUSIP → ticker resolution via OpenFIGI (free, no API key required)
# ---------------------------------------------------------------------------
_OPENFIGI_URL   = "https://api.openfigi.com/v3/mapping"
_CUSIP_CACHE    = _CACHE_DIR / "cusip_ticker_map.json"
_OPENFIGI_BATCH = 10    # max items per request without API key (free tier limit)
_OPENFIGI_SLEEP = 2.0   # seconds between batches

_cusip_map: dict[str, str] = {}     # in-memory layer; populated on first use


def _load_cusip_cache() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    global _cusip_map
    if _CUSIP_CACHE.exists() and not _cusip_map:
        _cusip_map = json.loads(_CUSIP_CACHE.read_text())


def _save_cusip_cache() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CUSIP_CACHE.write_text(json.dumps(_cusip_map))


def resolve_cusips(cusips: list[str]) -> dict[str, str]:
    """
    Map a list of CUSIP strings to US equity tickers via OpenFIGI.

    Returns a dict of {cusip: ticker} for successfully resolved CUSIPs.
    Results are cached permanently to .cache/edgar/cusip_ticker_map.json.
    CUSIPs that have no US equity listing are stored as "" so they are not
    re-queried on future runs.
    """
    _load_cusip_cache()

    todo = [c for c in cusips if c not in _cusip_map]
    if not todo:
        return {c: _cusip_map[c] for c in cusips if _cusip_map.get(c)}

    # Batch requests
    for i in range(0, len(todo), _OPENFIGI_BATCH):
        batch = todo[i : i + _OPENFIGI_BATCH]
        # No exchCode filter — it's not a market filter, just a specific code.
        # We prefer US common stocks in the response parsing instead.
        payload = [{"idType": "ID_CUSIP", "idValue": c} for c in batch]
        try:
            resp = requests.post(
                _OPENFIGI_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if resp.status_code == 429:   # rate limited
                time.sleep(60)
                resp = requests.post(_OPENFIGI_URL, json=payload,
                                     headers={"Content-Type": "application/json"}, timeout=30)
            if resp.status_code == 413:   # payload too large — shouldn't happen with batch=10
                data = [{}] * len(batch)
            else:
                data = resp.json()
        except Exception:
            data = [{}] * len(batch)

        for cusip, result in zip(batch, data):
            figi_list = result.get("data") or []
            ticker = ""

            # Priority: US-exchange common stock > any common stock > first result
            for priority in (
                lambda i: i.get("exchCode") == "US" and "Common" in i.get("securityType", ""),
                lambda i: "Common" in i.get("securityType", "") and i.get("marketSector") == "Equity",
                lambda i: i.get("marketSector") == "Equity",
            ):
                for item in figi_list:
                    if priority(item) and item.get("ticker"):
                        ticker = item["ticker"]
                        break
                if ticker:
                    break

            # Only store successful resolutions — never cache empty strings so
            # temporarily-unresolvable CUSIPs (data gaps, new listings) get
            # retried on future runs rather than being permanently excluded.
            if ticker:
                _cusip_map[cusip] = ticker.upper()

        if i + _OPENFIGI_BATCH < len(todo):
            time.sleep(_OPENFIGI_SLEEP)

    _save_cusip_cache()
    return {c: _cusip_map[c] for c in cusips if _cusip_map.get(c)}


# ---------------------------------------------------------------------------
# Per-filing download with disk cache
# ---------------------------------------------------------------------------
def _fetch_holdings_cached(cik: int, accession: str, primary_doc: str) -> list[dict]:
    """
    Download one N-PORT filing, parse it, resolve CUSIPs to tickers, and cache.

    Cache stores the final resolved list so CUSIP resolution is only done once
    per filing regardless of how many future calls reference it.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    acc_nd     = accession.replace("-", "")
    cache_file = _CACHE_DIR / f"holdings_{cik}_{acc_nd}.json"

    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        # Re-resolve if any entries still have no ticker (legacy cache)
        if cached and all(h.get("ticker") for h in cached):
            return cached

    url = f"{_ARC_BASE}/{cik}/{acc_nd}/primary_doc.xml"
    try:
        xml_text = _get(url).text
        holdings = _parse_nport_xml(xml_text)
    except Exception as exc:
        print(f"\n    Warning: could not fetch filing {accession}: {exc}")
        return []

    # Resolve CUSIPs to tickers for holdings that don't already have a ticker
    unresolved = [h for h in holdings if not h["ticker"] and h["cusip"]]
    if unresolved:
        cusips    = list({h["cusip"] for h in unresolved})
        cusip_map = resolve_cusips(cusips)
        for h in holdings:
            if not h["ticker"] and h["cusip"]:
                h["ticker"] = cusip_map.get(h["cusip"], "")

    # Drop holdings we still couldn't resolve
    holdings = [h for h in holdings if h["ticker"]]

    cache_file.write_text(json.dumps(holdings))
    return holdings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_constituent_history(
    ticker: str,
    start_date: str,
    end_date: str,
    top_n: Optional[int] = None,
    min_pct: float = 0.0,
) -> pd.DataFrame:
    """
    Fetch quarterly N-PORT constituent history for an ETF.

    Parameters
    ----------
    ticker     : ETF ticker (e.g. "XLF").
    start_date : ISO date string — fetches one quarter prior for warm-up.
    end_date   : ISO date string.
    top_n      : Keep only the top-N holdings by weight (None = all).
    min_pct    : Minimum portfolio weight % to include (default 0 = all).

    Returns
    -------
    DataFrame with columns:
        filing_date  : pd.Timestamp  (N-PORT report date, roughly monthly)
        constituents : list[str]     (tickers sorted by weight descending)
        weights      : list[float]   (portfolio % weights, same order)

    Notes
    -----
    N-PORT-P was introduced April 2019.  Filings before that date used the
    older N-Q format and are not fetched here.  For backtests starting before
    mid-2019, the earliest available N-PORT filing is used as a proxy.
    """
    cik, series_id = _resolve(ticker)
    label = f"{ticker} (CIK {cik}" + (f", series {series_id})" if series_id else ")")
    print(f"  Fetching N-PORT history for {label}...")

    filings = _get_filings(cik, series_id=series_id)
    if filings.empty:
        print(f"  No N-PORT-P filings found for {ticker}")
        return pd.DataFrame(columns=["filing_date", "constituents", "weights"])

    start = pd.Timestamp(start_date) - pd.DateOffset(months=4)
    end   = pd.Timestamp(end_date)
    mask  = (filings["filing_date"] >= start) & (filings["filing_date"] <= end)
    filings = filings[mask].reset_index(drop=True)

    if filings.empty:
        print(f"  No N-PORT filings in range {start_date} to {end_date} for {ticker}")
        return pd.DataFrame(columns=["filing_date", "constituents", "weights"])

    rows = []
    n = len(filings)
    for i, row in filings.iterrows():
        print(f"  [{i+1:2d}/{n}] {ticker} {row['filing_date'].date()} ...", end="\r")
        holdings = _fetch_holdings_cached(cik, row["accession"], row["primary_doc"])

        if min_pct > 0:
            holdings = [h for h in holdings if h["pct_val"] >= min_pct]
        if top_n:
            holdings = holdings[:top_n]

        if holdings:
            rows.append({
                "filing_date":  row["filing_date"],
                "constituents": [h["ticker"] for h in holdings],
                "weights":      [h["pct_val"]  for h in holdings],
            })

    print(f"  {ticker}: {len(rows)} N-PORT filings fetched ({start_date} to {end_date})      ")
    if not rows:
        return pd.DataFrame(columns=["filing_date", "constituents", "weights"])
    return pd.DataFrame(rows).sort_values("filing_date").reset_index(drop=True)


def get_constituents_at(history: pd.DataFrame, date: pd.Timestamp) -> list[str]:
    """
    Return the constituent list from the most recent filing on or before `date`.

    Falls back to the earliest available filing if `date` precedes all filings.
    Returns [] if `history` is empty.
    """
    if history.empty:
        return []
    prior = history[history["filing_date"] <= date]
    row   = prior.iloc[-1] if not prior.empty else history.iloc[0]
    return list(row["constituents"])


def summarize_changes(history: pd.DataFrame) -> pd.DataFrame:
    """
    Show constituent adds / removes between consecutive N-PORT filings.

    Returns DataFrame[filing_date, added, removed, n_total].
    """
    rows = []
    prev: set[str] = set()
    for _, row in history.iterrows():
        curr    = set(row["constituents"])
        added   = sorted(curr - prev)
        removed = sorted(prev - curr)
        rows.append({
            "filing_date": row["filing_date"],
            "added":       added,
            "removed":     removed,
            "n_total":     len(curr),
        })
        prev = curr
    return pd.DataFrame(rows)

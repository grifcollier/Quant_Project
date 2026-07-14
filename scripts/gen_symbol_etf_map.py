"""
Generate dashboard/lib/symbol_etf_map.json — a static {symbol: ETF} lookup so the
paper-trading dashboard can attribute constituent-stock fills to their sector ETF.

For each of the 5 traded ETFs, pull the full N-PORT constituent history and take the
union of every ticker that was ever a top-`TOP_N` holding (a wider net than the
hedge work's top-10, so the slowly-refreshed static map doesn't miss a name that
briefly entered a basket). Share classes are normalized to Alpaca's dot form
(BRK/B -> BRK.B). The 5 ETF tickers map to themselves.

Cross-sector collisions (a symbol in >1 ETF's history) are resolved to the ETF
where the symbol carried the higher mean portfolio weight, and EVERY collision is
printed (symbol, winner, margin) so the list can be eyeballed before the map is
trusted — sector ETFs are near-disjoint, so this should be short.

Usage:  python scripts/gen_symbol_etf_map.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data.edgar import build_constituent_history

ETFS = ["XLK", "XLF", "XLV", "XLI", "XLE"]
TOP_N = 15
OUT = Path(__file__).parents[1] / "dashboard" / "lib" / "symbol_etf_map.json"

# Symbols the live basket trades but that this script's N-PORT parse doesn't
# resolve to a clean ticker (so build_constituent_history never surfaces them).
# GOOGL/META are traded in the live XLK basket — verified by fill-day alignment:
# every GOOGL/META fill lands on the same day as the XLK tech names (AAPL/MSFT/
# NVDA), and XLK itself. Without this override they'd fall into an "Other" bucket
# on the dashboard's By-ETF tab. Re-verify (and prune) if the basket changes.
MANUAL_OVERRIDES = {"GOOGL": "XLK", "META": "XLK"}


def _norm(ticker: str) -> str:
    """EDGAR slash share-class -> Alpaca dot form (BRK/B -> BRK.B)."""
    return ticker.replace("/", ".").upper()


def main() -> None:
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=5)

    # symbol -> {etf: mean_weight} across each ETF's history
    weights: dict[str, dict[str, float]] = defaultdict(dict)

    for etf in ETFS:
        hist = build_constituent_history(
            etf, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), top_n=TOP_N
        )
        if hist.empty:
            print(f"  WARNING: no constituent history for {etf}")
            continue
        # accumulate per-symbol weight samples for this ETF
        acc: dict[str, list[float]] = defaultdict(list)
        for _, row in hist.iterrows():
            for tk, w in zip(row["constituents"], row["weights"]):
                if tk:
                    acc[_norm(tk)].append(float(w))
        for sym, ws in acc.items():
            weights[sym][etf] = sum(ws) / len(ws)

    # Build the map; resolve collisions by higher mean weight; collect collisions.
    mapping: dict[str, str] = {}
    collisions = []
    for sym, etf_w in weights.items():
        winner = max(etf_w, key=etf_w.get)
        mapping[sym] = winner
        if len(etf_w) > 1:
            ranked = sorted(etf_w.items(), key=lambda kv: kv[1], reverse=True)
            margin = ranked[0][1] - ranked[1][1]
            collisions.append((sym, winner, ranked, margin))

    # Manual overrides for names the N-PORT parse misses (see MANUAL_OVERRIDES).
    for sym, etf in MANUAL_OVERRIDES.items():
        mapping[sym] = etf

    # ETF tickers map to themselves (overrides any constituent hit, e.g. an ETF
    # rarely holding another ETF — not expected for these, but explicit is safer).
    for etf in ETFS:
        mapping[etf] = etf

    mapping = dict(sorted(mapping.items()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(mapping, indent=2) + "\n")

    print(f"\nWrote {len(mapping)} symbols -> {OUT}")
    if MANUAL_OVERRIDES:
        print("Manual overrides applied (N-PORT parse misses these): " +
              ", ".join(f"{s}->{e}" for s, e in MANUAL_OVERRIDES.items()))
    print(f"Per-ETF counts: " + ", ".join(
        f"{e}={sum(1 for v in mapping.values() if v == e)}" for e in ETFS))

    print(f"\n{'='*64}\nCROSS-ETF COLLISIONS (eyeball before trusting the map)\n{'='*64}")
    if not collisions:
        print("  None — every symbol appeared in exactly one ETF's history.")
    else:
        collisions.sort(key=lambda c: c[3])  # smallest margin first (most suspect)
        for sym, winner, ranked, margin in collisions:
            detail = "  ".join(f"{e}={w:.2f}%" for e, w in ranked)
            flag = "  <-- CLOSE, CHECK" if margin < 1.0 else ""
            print(f"  {sym:<7} -> {winner:<4} (margin {margin:5.2f}pp)   [{detail}]{flag}")
        print(f"\n  {len(collisions)} collision(s). Small-margin ones are the ones to verify.")


if __name__ == "__main__":
    main()

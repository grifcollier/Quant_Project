"""
Daily basket trading automation script.
Run after market close (4:30pm ET) via Windows Task Scheduler.

Usage:
    python scripts/daily_trade.py            # dry-run (preview only)
    python scripts/daily_trade.py --execute  # place real paper orders
"""

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# ── Basket configuration ──────────────────────────────────────────────────────
BASKETS = [
    {"etf": "XLF", "stocks": ["GS",   "MS",   "JPM",   "BAC",  "C"  ]},
    {"etf": "XLV", "stocks": ["UNH",  "LLY",  "ABBV",  "JNJ",  "MRK"]},
    {"etf": "XLI", "stocks": ["GE",   "RTX",  "CAT",   "HON",  "UPS"]},
    {"etf": "XLK", "stocks": ["MSFT", "AAPL", "NVDA",  "GOOGL","META"]},
    {"etf": "XLE", "stocks": ["XOM",  "CVX",  "COP",   "SLB",  "EOG"]},
]

Z_ENTRY = 1.5
Z_EXIT  = 0.25
Z_STOP  = 2.5
WINDOW  = 60

# ── Setup ─────────────────────────────────────────────────────────────────────
EXECUTE   = "--execute" in sys.argv
ROOT      = Path(__file__).parents[1]
LOG_DIR   = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE  = LOG_DIR / f"trade_{datetime.today().strftime('%Y-%m-%d')}.log"

def log(msg: str):
    ts  = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_basket(etf: str, stocks: list) -> dict:
    """Run trade command for one basket, return parsed result."""
    cmd = [
        sys.executable, str(ROOT / "run.py"),
        "trade", "--strategy", "basket",
        "--etf", etf,
        "--stocks", *stocks,
        "--z-entry", str(Z_ENTRY),
        "--z-exit",  str(Z_EXIT),
        "--z-stop",  str(Z_STOP),
        "--window",  str(WINDOW),
    ]
    if EXECUTE:
        cmd.append("--execute")

    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ)
    output = result.stdout + result.stderr

    # Parse key fields from output
    signal    = "UNKNOWN"
    z_score   = None
    n_orders  = 0
    for line in output.splitlines():
        if "Signal:" in line:
            signal = line.split("Signal:")[-1].strip()
        if "Z-score:" in line:
            try:
                z_score = float(line.split()[1])
            except Exception:
                pass
        if "submitted" in line:
            n_orders += 1

    return {
        "etf":      etf,
        "signal":   signal,
        "z_score":  z_score,
        "n_orders": n_orders,
        "output":   output,
        "error":    result.returncode != 0,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    mode = "EXECUTE" if EXECUTE else "DRY-RUN"
    log(f"{'='*55}")
    log(f"Daily basket trade — {datetime.today().strftime('%Y-%m-%d')}  [{mode}]")
    log(f"{'='*55}")

    if not os.environ.get("ALPACA_API_KEY"):
        log("WARNING: ALPACA_API_KEY not set — will use yfinance for prices.")
    if EXECUTE and not os.environ.get("ALPACA_PAPER_KEY"):
        log("ERROR: ALPACA_PAPER_KEY not set — cannot place orders. Aborting.")
        sys.exit(1)

    results = []
    for b in BASKETS:
        log(f"\nRunning {b['etf']} basket...")
        r = run_basket(b["etf"], b["stocks"])

        # Log full output indented
        for line in r["output"].splitlines():
            log(f"  {line}")

        if r["error"]:
            log(f"  !! ERROR running {b['etf']} basket")
        results.append(r)

    # ── Summary table ─────────────────────────────────────────────────────────
    log(f"\n{'='*55}")
    log(f"SUMMARY")
    log(f"{'='*55}")
    log(f"  {'ETF':<6} {'Z-score':>8}  {'Signal':<30}  {'Orders':>6}")
    log(f"  {'-'*6} {'-'*8}  {'-'*30}  {'-'*6}")
    for r in results:
        z_str = f"{r['z_score']:+.2f}" if r["z_score"] is not None else "  n/a"
        orders_str = str(r["n_orders"]) if EXECUTE else "-"
        log(f"  {r['etf']:<6} {z_str:>8}  {r['signal']:<30}  {orders_str:>6}")

    total_orders = sum(r["n_orders"] for r in results)
    log(f"\n  Total orders placed: {total_orders}")
    log(f"  Log written to: {LOG_FILE}")
    log(f"{'='*55}")


if __name__ == "__main__":
    main()

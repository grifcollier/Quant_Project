"""
Pre-compute Plotly figures for the Streamlit app.
Run once locally before pushing; the JSON files are committed to the repo
so the Streamlit Community Cloud app loads instantly without re-running backtests.

Usage:
    python scripts/precompute_streamlit.py
"""
import subprocess
import sys
from pathlib import Path

ROOT    = Path(__file__).parent.parent
PYTHON  = sys.executable
OUT     = ROOT / "streamlit_app" / "precomputed"

BASKETS = ["--basket", "XLF:", "--basket", "XLV:", "--basket", "XLI:",
           "--basket", "XLK:", "--basket", "XLE:"]


def run(label: str, cmd: list[str]) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"\nERROR: '{label}' failed (exit {result.returncode})")
        sys.exit(1)


if __name__ == "__main__":
    # 1. Multi-basket portfolio + Monte Carlo (no walk-forward — they share the same run gate)
    portfolio_dir = OUT / "portfolio"
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    run("Multi-basket portfolio + Monte Carlo", [
        PYTHON, "run.py", "basket-multi",
        "--period", "5y", "--monte-carlo",
        *BASKETS,
        "--save-figs", str(portfolio_dir),
    ])

    # 2. Multi-basket walk-forward
    wf_dir = OUT / "walkforward"
    wf_dir.mkdir(parents=True, exist_ok=True)
    run("Multi-basket walk-forward (4 folds)", [
        PYTHON, "run.py", "basket-multi",
        "--period", "5y", "--walk-forward",
        *BASKETS,
        "--save-figs", str(wf_dir),
    ])

    # 3. XLK single basket
    xlk_dir = OUT / "xlk"
    xlk_dir.mkdir(parents=True, exist_ok=True)
    run("XLK single basket", [
        PYTHON, "run.py", "basket",
        "--etf", "XLK", "--period", "5y",
        "--save-figs", str(xlk_dir),
    ])

    # 4. 10y multi-basket portfolio + Monte Carlo
    portfolio_10y_dir = OUT / "portfolio_10y"
    portfolio_10y_dir.mkdir(parents=True, exist_ok=True)
    run("10y Multi-basket portfolio + Monte Carlo", [
        PYTHON, "run.py", "basket-multi",
        "--period", "10y", "--monte-carlo",
        *BASKETS,
        "--save-figs", str(portfolio_10y_dir),
    ])

    # 5. 10y Multi-basket walk-forward
    wf_10y_dir = OUT / "walkforward_10y"
    wf_10y_dir.mkdir(parents=True, exist_ok=True)
    run("10y Multi-basket walk-forward", [
        PYTHON, "run.py", "basket-multi",
        "--period", "10y", "--walk-forward",
        *BASKETS,
        "--save-figs", str(wf_10y_dir),
    ])

    # 6. 10y XLK single basket
    xlk_10y_dir = OUT / "xlk_10y"
    xlk_10y_dir.mkdir(parents=True, exist_ok=True)
    run("10y XLK single basket", [
        PYTHON, "run.py", "basket",
        "--etf", "XLK", "--period", "10y",
        "--save-figs", str(xlk_10y_dir),
    ])

    print("\nAll figures saved to", OUT)
    print("  Commit the streamlit_app/precomputed/ directory to the repo.")

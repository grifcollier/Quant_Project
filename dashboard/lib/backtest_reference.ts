/**
 * Static reference numbers from the Python backtester, mirrored from the
 * Streamlit app (`app.py`) so the dashboard can show backtest vs live paper
 * side-by-side. These are PRECOMPUTED offline (the Next.js runtime can't run
 * the Python backtest) — regenerate the backtest and update these values when
 * the strategy or data window changes.
 *
 * Source of truth: `app.py` key-metrics + walk-forward + Monte-Carlo sections,
 * produced by `python scripts/precompute_streamlit.py` (combined 5-ETF
 * portfolio, portfolio_engine, $20k per ETF = $100k total, cost 5bps).
 * Metrics use the same formulas as the dashboard's analytics.ts
 * (daily-equity Sharpe √252 ddof=1; one trade = one basket spread round-trip).
 */

export interface Fold {
  label: string;
  ret: number;    // fold total return (fraction)
  sharpe: number; // fold Sharpe
}

export interface BacktestPeriod {
  key: '5y' | '10y';
  label: string;
  years: number;
  totalReturn: number;   // combined 5-ETF portfolio total return (fraction)
  sharpe: number;        // combined portfolio Sharpe
  maxDrawdown: number;   // worst peak-to-trough (fraction, negative)
  oosReturn: number;     // stitched walk-forward OOS return (fraction)
  oosLabel: string;      // e.g. "4 folds × 1y"
  monteCarlo: { p5: number; median: number; p95: number }; // 10k bootstrap sims
  folds: Fold[];         // per rolling-window (walk-forward) fold
}

// ── Combined-portfolio results ────────────────────────────────────────────────
export const BACKTEST: Record<'5y' | '10y', BacktestPeriod> = {
  '5y': {
    key: '5y',
    label: '5-year',
    years: 5,
    totalReturn: 0.422,
    sharpe: 4.59,
    maxDrawdown: -0.007,
    oosReturn: 0.336,
    oosLabel: '4 folds × 1y',
    monteCarlo: { p5: 0.343, median: 0.421, p95: 0.509 },
    folds: [
      { label: 'Fold 1', ret: 0.060, sharpe: 4.12 },
      { label: 'Fold 2', ret: 0.082, sharpe: 5.40 },
      { label: 'Fold 3', ret: 0.087, sharpe: 4.80 },
      { label: 'Fold 4', ret: 0.107, sharpe: 5.07 },
    ],
  },
  '10y': {
    key: '10y',
    label: '10-year',
    years: 10,
    totalReturn: 0.912,
    sharpe: 4.61,
    maxDrawdown: -0.007,
    oosReturn: 0.819,
    oosLabel: '9 folds × 1y',
    monteCarlo: { p5: 0.777, median: 0.910, p95: 1.062 },
    folds: [
      { label: 'Fold 1', ret: 0.110, sharpe: 5.43 },
      { label: 'Fold 2', ret: 0.122, sharpe: 5.18 },
      { label: 'Fold 3', ret: 0.099, sharpe: 3.98 },
      { label: 'Fold 4', ret: 0.067, sharpe: 3.66 },
      { label: 'Fold 5', ret: 0.086, sharpe: 4.74 },
      { label: 'Fold 6', ret: 0.060, sharpe: 4.12 },
      { label: 'Fold 7', ret: 0.082, sharpe: 5.40 },
      { label: 'Fold 8', ret: 0.087, sharpe: 4.80 },
      { label: 'Fold 9', ret: 0.107, sharpe: 5.07 },
    ],
  },
};

/** Annualize a cumulative return over `years`: CAGR = (1+total)^(1/years) - 1. */
export const annualize = (total: number, years: number) => Math.pow(1 + total, 1 / years) - 1;

export const BACKTEST_META = {
  capital: 100_000, // 5 ETFs × $20k
  costBps: 5,
  note: 'Combined 5-ETF portfolio · EDGAR N-PORT constituents · walk-forward validated',
  regenerate: 'python scripts/precompute_streamlit.py',
};

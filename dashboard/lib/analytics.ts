/**
 * Performance analytics mirroring the Python backtester (`src/backtest/metrics.py`)
 * so live paper-trading numbers are directly comparable to backtest numbers.
 *
 * Conventions (identical to metrics.py):
 *   - returns  = equity.pct_change()  (simple, not log)
 *   - Sharpe   = mean/std * sqrt(252), risk-free = 0, sample std (ddof=1)
 *   - Sortino  = mean(all days) / std(negative days only) * sqrt(252)
 *   - maxDD    = min(equity / cummax - 1)   (negative fraction)
 */

const TRADING_DAYS = 252;
const ANN = Math.sqrt(TRADING_DAYS);

export function mean(xs: number[]): number {
  return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : 0;
}

/** Sample standard deviation (ddof=1), matching pandas `.std()`. */
export function sampleStd(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  const ss = xs.reduce((s, x) => s + (x - m) * (x - m), 0);
  return Math.sqrt(ss / (xs.length - 1));
}

/** equity[i]/equity[i-1] - 1 for i in 1..n-1 (drops the first point). */
export function pctChange(equity: number[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < equity.length; i++) {
    const prev = equity[i - 1];
    if (prev !== 0 && Number.isFinite(prev) && Number.isFinite(equity[i])) {
      out.push(equity[i] / prev - 1);
    }
  }
  return out;
}

/** Annualized Sharpe of a daily-return series (RF=0). 0 when undefined. */
export function sharpe(returns: number[]): number {
  const sd = sampleStd(returns);
  if (returns.length < 2 || sd <= 0) return 0;
  return (mean(returns) / sd) * ANN;
}

/** Annualized Sortino — denominator is std of the negative-return subset only. */
export function sortino(returns: number[]): number {
  const downside = sampleStd(returns.filter((r) => r < 0));
  if (returns.length < 2 || downside <= 0) return 0;
  return (mean(returns) / downside) * ANN;
}

/** Max drawdown as a negative fraction: min(equity/runningMax - 1). */
export function maxDrawdown(equity: number[]): number {
  let peak = -Infinity;
  let mdd = 0;
  for (const e of equity) {
    if (e > peak) peak = e;
    if (peak > 0) mdd = Math.min(mdd, e / peak - 1);
  }
  return mdd;
}

export interface DrawdownPoint {
  t: number; // epoch seconds
  ddPct: number; // (equity/cummax - 1) * 100  (<= 0)
}

/** Full drawdown series in percent, for the drawdown chart. */
export function drawdownSeries(timestamps: number[], equity: number[]): DrawdownPoint[] {
  let peak = -Infinity;
  const out: DrawdownPoint[] = [];
  for (let i = 0; i < equity.length; i++) {
    const e = equity[i];
    if (!Number.isFinite(e)) continue;
    if (e > peak) peak = e;
    out.push({ t: timestamps[i], ddPct: peak > 0 ? (e / peak - 1) * 100 : 0 });
  }
  return out;
}

/** Current drawdown from the running peak, as a negative fraction. */
export function currentDrawdown(equity: number[]): number {
  const valid = equity.filter((e) => Number.isFinite(e));
  if (!valid.length) return 0;
  const peak = Math.max(...valid);
  return peak > 0 ? valid[valid.length - 1] / peak - 1 : 0;
}

export function totalReturn(equity: number[]): number {
  const valid = equity.filter((e) => Number.isFinite(e) && e > 0);
  if (valid.length < 2) return 0;
  return valid[valid.length - 1] / valid[0] - 1;
}

export interface MonthlyMetric {
  key: string; // YYYY-MM
  label: string; // "Jan 25"
  sharpe: number;
  sortino: number;
  ret: number; // compounded monthly return (fraction)
  tradingDays: number;
}

function monthKey(epochSec: number): string {
  const d = new Date(epochSec * 1000);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

function monthLabel(key: string): string {
  const [y, m] = key.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1)).toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  });
}

/**
 * Per-calendar-month Sharpe/Sortino (annualized) and compounded return, from the
 * daily equity series. `tradingDays` is carried so the UI can flag thin months —
 * a single month has ~21 obs and its annualized Sharpe is noisy.
 */
export function monthlyMetrics(timestamps: number[], equity: number[]): MonthlyMetric[] {
  // Daily returns aligned to the day they were realized (timestamps[1..]).
  const buckets: Record<string, number[]> = {};
  for (let i = 1; i < equity.length; i++) {
    const prev = equity[i - 1];
    if (prev === 0 || !Number.isFinite(prev) || !Number.isFinite(equity[i])) continue;
    const key = monthKey(timestamps[i]);
    (buckets[key] ??= []).push(equity[i] / prev - 1);
  }
  return Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, rets]) => ({
      key,
      label: monthLabel(key),
      sharpe: sharpe(rets),
      sortino: sortino(rets),
      ret: rets.reduce((acc, r) => acc * (1 + r), 1) - 1,
      tradingDays: rets.length,
    }));
}

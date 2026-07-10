'use client';

import { useState } from 'react';
import { StatCard, Card, fmtPct } from '../components/ui';
import { SvgBarChart, SvgLineChart, SvgGroupedBar, SegmentedControl, type BarDatum } from '../components/charts';
import type { MonthlyMetric, DrawdownPoint } from '@/lib/analytics';
import type { LegPeriod, TradeSummary } from '@/lib/trades';

interface Overall {
  sharpe: number;
  sortino: number;
  maxDD: number;
  curDD: number;
  totalRet: number;
}

const THIN_MONTH = 15; // fewer daily obs than this = de-emphasized (noisy Sharpe)

type MetricKey = 'sharpe' | 'sortino' | 'ret';
const METRICS: { key: MetricKey; label: string }[] = [
  { key: 'sharpe', label: 'Sharpe' },
  { key: 'sortino', label: 'Sortino' },
  { key: 'ret', label: 'Return' },
];

export default function AnalyticsClient({
  overall,
  monthly,
  drawdown,
  legs,
  summary,
  hasEquity,
}: {
  overall: Overall;
  monthly: MonthlyMetric[];
  drawdown: DrawdownPoint[];
  legs: LegPeriod[];
  summary: TradeSummary;
  hasEquity: boolean;
}) {
  const [metric, setMetric] = useState<MetricKey>('sharpe');

  const isRet = metric === 'ret';
  const monthlyBars: BarDatum[] = monthly.map((m) => ({
    label: m.label,
    value: m[metric],
    dimmed: m.tradingDays < THIN_MONTH,
    note: `${m.tradingDays}d`,
  }));
  const barFmtVal = (v: number) => (isRet ? fmtPct(v) : v.toFixed(2));
  const barFmtTick = (v: number) => (isRet ? `${(v * 100).toFixed(0)}%` : v.toFixed(1));

  const ddPoints = drawdown.map((d) => ({
    label: new Date(d.t * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    value: d.ddPct,
  }));

  const legData = legs.map((l) => ({ label: l.label, a: l.etfPl, b: l.basketPl }));

  return (
    <div className="space-y-8">
      {/* KPI tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-4">
        <StatCard label="Sharpe (daily)" value={hasEquity ? overall.sharpe.toFixed(2) : '—'} positive={overall.sharpe >= 0} />
        <StatCard label="Sortino (daily)" value={hasEquity ? overall.sortino.toFixed(2) : '—'} positive={overall.sortino >= 0} />
        <StatCard label="Max Drawdown" value={hasEquity ? `${(overall.maxDD * 100).toFixed(2)}%` : '—'} positive={false} />
        <StatCard label="Current DD" value={hasEquity ? `${(overall.curDD * 100).toFixed(2)}%` : '—'} positive={overall.curDD >= 0} />
        <StatCard label="Total Return" value={hasEquity ? fmtPct(overall.totalRet) : '—'} positive={overall.totalRet >= 0} />
        <StatCard label="Profit Factor" value={summary.profitFactor != null ? summary.profitFactor.toFixed(2) : summary.tradeCount ? '∞' : '—'} />
        <StatCard label="Win Rate" value={summary.tradeCount ? `${summary.winRate.toFixed(0)}%` : '—'} sub={summary.tradeCount ? `${summary.tradeCount} trades` : undefined} />
      </div>

      {/* Monthly Sharpe / Sortino / Return */}
      <Card>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-base font-medium text-zinc-300">Monthly {METRICS.find((m) => m.key === metric)!.label}</h2>
          <SegmentedControl options={METRICS} value={metric} onChange={setMetric} />
        </div>
        <SvgBarChart data={monthlyBars} signed fmtVal={barFmtVal} fmtTick={barFmtTick} />
        {!isRet && (
          <p className="text-zinc-500 text-xs mt-2 leading-relaxed">
            Monthly Sharpe/Sortino annualize ~21 daily returns — single months are <span className="text-zinc-400">noisy</span>, and a
            couple of unusual days can swing a bar. Read the trend, not one month. Faded bars are thin months (&lt;{THIN_MONTH} trading
            days); hover any bar for its day count.
          </p>
        )}
      </Card>

      {/* Drawdown curve */}
      <Card>
        <h2 className="text-base font-medium text-zinc-300 mb-1">Drawdown</h2>
        <SvgLineChart data={ddPoints} fmtVal={(v) => `${v.toFixed(2)}%`} fmtTick={(v) => `${v.toFixed(0)}%`} />
        <p className="text-zinc-500 text-xs mt-2">Peak-to-trough decline of account equity (daily). Deepest point = max drawdown.</p>
      </Card>

      {/* ETF leg vs basket leg */}
      <Card>
        <h2 className="text-base font-medium text-zinc-300 mb-1">Realized P&amp;L by Leg</h2>
        <SvgGroupedBar data={legData} aLabel="ETF leg" bLabel="Basket leg" fmtVal={(v) => `${v >= 0 ? '+' : '-'}$${Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`} fmtTick={(v) => `$${(v / 1000).toFixed(1)}k`} />
        <p className="text-zinc-500 text-xs mt-2">
          Realized P&amp;L split between the ETF-ticker legs and the constituent-stock (basket) legs, by month.
        </p>
      </Card>
    </div>
  );
}

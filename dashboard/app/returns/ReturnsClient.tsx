'use client';

import { useState, useMemo } from 'react';
import { StatCard } from '../components/ui';
import type { PeriodStats } from '@/lib/trades';

type Granularity = 'daily' | 'weekly' | 'monthly';
type MetricKey   = 'realizedPl' | 'winRate' | 'avgReturn' | 'avgHoldDays';
type Timeframe   = '30' | '90' | '180' | '365' | 'all';

interface Overall {
  totalPl: number;
  winRate: number;
  avgReturn: number;
  avgHoldDays: number;
  tradeCount: number;
}

interface Props {
  daily:   PeriodStats[];
  weekly:  PeriodStats[];
  monthly: PeriodStats[];
  overall: Overall;
}

const METRICS = [
  {
    key: 'realizedPl' as MetricKey,
    label: 'Realized P&L',
    fmtVal:  (v: number) => `${v >= 0 ? '+' : '-'}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
    fmtTick: (v: number) => { const s = v > 0 ? '+' : v < 0 ? '-' : ''; const a = Math.abs(v); return a >= 1000 ? `${s}$${(a / 1000).toFixed(1)}k` : `${s}$${a.toFixed(0)}`; },
    signed: true,
  },
  {
    key: 'winRate' as MetricKey,
    label: 'Win Rate',
    fmtVal:  (v: number) => `${v.toFixed(1)}%`,
    fmtTick: (v: number) => `${v.toFixed(0)}%`,
    signed: false,
  },
  {
    key: 'avgReturn' as MetricKey,
    label: 'Avg Return',
    fmtVal:  (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`,
    fmtTick: (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`,
    signed: true,
  },
  {
    key: 'avgHoldDays' as MetricKey,
    label: 'Avg Hold Days',
    fmtVal:  (v: number) => `${v.toFixed(1)}d`,
    fmtTick: (v: number) => `${v.toFixed(0)}d`,
    signed: false,
  },
] as const;

const TIMEFRAMES = [
  { key: '30'  as Timeframe, label: '30D', days: 30   },
  { key: '90'  as Timeframe, label: '90D', days: 90   },
  { key: '180' as Timeframe, label: '6M',  days: 180  },
  { key: '365' as Timeframe, label: '1Y',  days: 365  },
  { key: 'all' as Timeframe, label: 'All', days: null },
] as const;

const GRANULARITIES = [
  { key: 'daily'   as Granularity, label: 'Daily'   },
  { key: 'weekly'  as Granularity, label: 'Weekly'  },
  { key: 'monthly' as Granularity, label: 'Monthly' },
] as const;

function filterByTimeframe(data: PeriodStats[], days: number | null): PeriodStats[] {
  if (!days) return data;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffDay   = cutoff.toISOString().slice(0, 10);
  const cutoffMonth = cutoff.toISOString().slice(0, 7);
  return data.filter(d => d.key.length === 7 ? d.key >= cutoffMonth : d.key >= cutoffDay);
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex gap-1">
      {options.map(o => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
            value === o.key
              ? 'bg-zinc-700 text-zinc-100 font-medium'
              : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function BarChart({
  data,
  metric,
}: {
  data: PeriodStats[];
  metric: typeof METRICS[number];
}) {
  const [hovered, setHovered] = useState<number | null>(null);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-36 text-zinc-500 text-sm">
        No data for this timeframe
      </div>
    );
  }

  const MAX_BARS = 60;
  const visible  = data.slice(-MAX_BARS);

  const W   = 800, H = 280;
  const pad = { top: 24, right: 16, bottom: 56, left: 70 };
  const iW  = W - pad.left - pad.right;
  const iH  = H - pad.top  - pad.bottom;

  const values = visible.map(d => d[metric.key] as number);
  const minV   = metric.signed ? Math.min(0, ...values) : 0;
  const maxV   = Math.max(0, ...values);
  const range  = maxV - minV || 0.01;

  const toY   = (v: number) => pad.top + iH * ((maxV - v) / range);
  const zeroY = toY(0);

  const tickCount = 5;
  const ticks = Array.from({ length: tickCount }, (_, i) => minV + (range / (tickCount - 1)) * i);

  const slotW      = iW / visible.length;
  const barW       = slotW * 0.82;
  const labelEvery = Math.max(1, Math.ceil(visible.length / 12));

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}>
      {/* Y gridlines + labels */}
      {ticks.map((tick, i) => {
        const y      = toY(tick);
        const isZero = Math.abs(tick) < 0.001 * (range || 1);
        return (
          <g key={i}>
            <line
              x1={pad.left} x2={W - pad.right} y1={y} y2={y}
              stroke={isZero ? '#52525b' : '#27272a'}
              strokeWidth={isZero ? 1 : 0.5}
            />
            <text x={pad.left - 6} y={y + 4} textAnchor="end" fontSize={10} fill="#71717a">
              {metric.fmtTick(tick)}
            </text>
          </g>
        );
      })}

      <line x1={pad.left} x2={pad.left} y1={pad.top} y2={H - pad.bottom} stroke="#3f3f46" strokeWidth={0.5} />

      {visible.map((d, i) => {
        const v    = d[metric.key] as number;
        const x    = pad.left + i * slotW + slotW * 0.09;
        const bH   = Math.abs(toY(v) - zeroY);
        const bY   = v >= 0 ? zeroY - bH : zeroY;
        const fill = !metric.signed ? '#818cf8' : v >= 0 ? '#34d399' : '#f87171';
        const cx   = x + barW / 2;
        const isHovered = hovered === i;

        const tipW = 90, tipH = 30;
        const tipX = Math.min(Math.max(cx - tipW / 2, pad.left), W - pad.right - tipW);
        const tipY = Math.max(4, Math.min(bY, zeroY) - tipH - 6);

        return (
          <g key={i} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}>
            <rect
              x={x} y={bY}
              width={barW} height={Math.max(1, bH)}
              fill={fill}
              opacity={hovered !== null && !isHovered ? 0.3 : 1}
              rx={barW > 6 ? 2 : 0}
            />

            {i % labelEvery === 0 && (
              <text
                x={cx}
                y={H - pad.bottom + 14}
                textAnchor={visible.length > 20 ? 'end' : 'middle'}
                fontSize={9}
                fill="#71717a"
                transform={visible.length > 20 ? `rotate(-45, ${cx}, ${H - pad.bottom + 14})` : undefined}
              >
                {d.label}
              </text>
            )}

            {isHovered && (
              <g>
                <rect x={tipX} y={tipY} width={tipW} height={tipH} fill="#27272a" rx={4} stroke="#3f3f46" strokeWidth={1} />
                <text x={tipX + tipW / 2} y={tipY + 13} textAnchor="middle" fontSize={11} fill="#e4e4e7" fontWeight="500">
                  {metric.fmtVal(v)}
                </text>
                <text x={tipX + tipW / 2} y={tipY + 25} textAnchor="middle" fontSize={9} fill="#71717a">
                  {d.label} · {d.tradeCount} trade{d.tradeCount !== 1 ? 's' : ''}
                </text>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export default function ReturnsClient({ daily, weekly, monthly, overall }: Props) {
  // One shared granularity drives both the chart and the Period Breakdown table,
  // so switching Daily/Weekly/Monthly in either place keeps them in sync.
  const [granularity, setGranularity] = useState<Granularity>('weekly');
  const [metricKey,   setMetricKey  ] = useState<MetricKey>('realizedPl');
  const [timeframe,   setTimeframe  ] = useState<Timeframe>('all');

  const metric = METRICS.find(m => m.key === metricKey)!;
  const tfDays = TIMEFRAMES.find(t => t.key === timeframe)!.days;

  const chartData = useMemo(() => {
    const d = granularity === 'daily' ? daily : granularity === 'weekly' ? weekly : monthly;
    return filterByTimeframe(d, tfDays);
  }, [granularity, tfDays, daily, weekly, monthly]);

  const tableData = useMemo(() => {
    const d = granularity === 'daily' ? daily : granularity === 'weekly' ? weekly : monthly;
    return [...d].reverse().slice(0, 20);
  }, [granularity, daily, weekly, monthly]);

  const fmtPl = (v: number) =>
    `${v >= 0 ? '+' : '-'}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="space-y-8">
      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard
          label="Total Realized P&L"
          value={overall.tradeCount > 0 ? fmtPl(overall.totalPl) : '—'}
          positive={overall.tradeCount > 0 ? overall.totalPl >= 0 : undefined}
        />
        <StatCard
          label="Win Rate"
          value={overall.tradeCount > 0 ? `${overall.winRate.toFixed(1)}%` : '—'}
          sub={overall.tradeCount > 0 ? `${overall.tradeCount} trades` : undefined}
        />
        <StatCard
          label="Avg Return / Trade"
          value={overall.tradeCount > 0 ? `${overall.avgReturn >= 0 ? '+' : ''}${overall.avgReturn.toFixed(2)}%` : '—'}
          positive={overall.tradeCount > 0 ? overall.avgReturn >= 0 : undefined}
        />
        <StatCard
          label="Avg Hold Days"
          value={overall.tradeCount > 0 ? overall.avgHoldDays.toFixed(1) : '—'}
        />
      </div>

      {/* Chart */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-y-3 mb-5">
          <div className="flex gap-1 flex-wrap">
            {METRICS.map(m => (
              <button
                key={m.key}
                onClick={() => setMetricKey(m.key)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  metricKey === m.key
                    ? 'bg-zinc-700 text-zinc-100'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <div className="flex gap-3 flex-wrap">
            <SegmentedControl options={GRANULARITIES} value={granularity} onChange={setGranularity} />
            <SegmentedControl options={TIMEFRAMES}    value={timeframe}   onChange={setTimeframe}   />
          </div>
        </div>
        <BarChart data={chartData} metric={metric} />
      </div>

      {/* Period breakdown table */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-medium text-zinc-300">Period Breakdown</h2>
          <SegmentedControl options={GRANULARITIES} value={granularity} onChange={setGranularity} />
        </div>

        {tableData.length === 0 ? (
          <p className="text-zinc-500 text-sm py-4">No trade data yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-zinc-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/60">
                  {['Period', 'Trades', 'Realized P&L', 'Win Rate', 'Avg Return', 'Avg Hold'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableData.map(row => (
                  <tr key={row.key} className="border-b border-zinc-800/60 last:border-0 hover:bg-zinc-800/30 transition-colors">
                    <td className="px-4 py-3 text-zinc-200 whitespace-nowrap font-medium">{row.label}</td>
                    <td className="px-4 py-3 text-zinc-400 tabular-nums">{row.tradeCount}</td>
                    <td className={`px-4 py-3 tabular-nums font-medium ${row.realizedPl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {fmtPl(row.realizedPl)}
                    </td>
                    <td className="px-4 py-3 text-zinc-300 tabular-nums">{row.winRate.toFixed(1)}%</td>
                    <td className={`px-4 py-3 tabular-nums ${row.avgReturn >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {`${row.avgReturn >= 0 ? '+' : ''}${row.avgReturn.toFixed(2)}%`}
                    </td>
                    <td className="px-4 py-3 text-zinc-300 tabular-nums">{row.avgHoldDays.toFixed(1)}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

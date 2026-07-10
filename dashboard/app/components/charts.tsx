'use client';

import { useState } from 'react';

/**
 * Hand-rolled SVG charts (the dashboard has no charting library). Conventions
 * match the original bar chart in returns/ReturnsClient.tsx: 800x280 viewBox,
 * emerald/red/indigo fills, zinc gridlines, hover tooltips.
 */

const GREEN = '#34d399';
const RED = '#f87171';
const INDIGO = '#818cf8';
const BLUE = '#60a5fa';
const GRID = '#27272a';
const ZERO = '#52525b';
const AXIS = '#3f3f46';
const TICKTXT = '#71717a';

const W = 800;
const H = 280;
const PAD = { top: 24, right: 16, bottom: 56, left: 70 };
const IW = W - PAD.left - PAD.right;
const IH = H - PAD.top - PAD.bottom;

function Empty({ msg }: { msg: string }) {
  return <div className="flex items-center justify-center h-36 text-zinc-500 text-sm">{msg}</div>;
}

/** Small pill toggle (matches the one in returns/ReturnsClient). */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg bg-zinc-900 border border-zinc-800 p-0.5">
      {options.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={`px-3 py-1 text-xs rounded-md transition-colors ${
            value === o.key ? 'bg-zinc-700 text-zinc-100 font-medium' : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function yScale(minV: number, maxV: number) {
  const range = maxV - minV || 0.01;
  const toY = (v: number) => PAD.top + IH * ((maxV - v) / range);
  return { toY, range };
}

function gridlines(minV: number, maxV: number, toY: (v: number) => number, fmtTick: (v: number) => string) {
  const range = maxV - minV || 0.01;
  const ticks = Array.from({ length: 5 }, (_, i) => minV + (range / 4) * i);
  return (
    <>
      {ticks.map((tick, i) => {
        const y = toY(tick);
        const isZero = Math.abs(tick) < 0.001 * range;
        return (
          <g key={i}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} stroke={isZero ? ZERO : GRID} strokeWidth={isZero ? 1 : 0.5} />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize={10} fill={TICKTXT}>
              {fmtTick(tick)}
            </text>
          </g>
        );
      })}
      <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={H - PAD.bottom} stroke={AXIS} strokeWidth={0.5} />
    </>
  );
}

export interface BarDatum {
  label: string;
  value: number;
  dimmed?: boolean; // e.g. a thin/low-confidence month
  note?: string; // extra tooltip line
}

/** Signed bar chart (green +/red -), or single-color when signed=false. */
export function SvgBarChart({
  data,
  signed = true,
  fmtVal,
  fmtTick,
  maxBars = 60,
}: {
  data: BarDatum[];
  signed?: boolean;
  fmtVal: (v: number) => string;
  fmtTick: (v: number) => string;
  maxBars?: number;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  if (data.length === 0) return <Empty msg="No data" />;

  const visible = data.slice(-maxBars);
  const values = visible.map((d) => d.value);
  const minV = signed ? Math.min(0, ...values) : 0;
  const maxV = Math.max(0, ...values);
  const { toY } = yScale(minV, maxV);
  const zeroY = toY(0);
  const slotW = IW / visible.length;
  const barW = slotW * 0.82;
  const labelEvery = Math.max(1, Math.ceil(visible.length / 12));

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}>
      {gridlines(minV, maxV, toY, fmtTick)}
      {visible.map((d, i) => {
        const v = d.value;
        const x = PAD.left + i * slotW + slotW * 0.09;
        const bH = Math.abs(toY(v) - zeroY);
        const bY = v >= 0 ? zeroY - bH : zeroY;
        const fill = !signed ? INDIGO : v >= 0 ? GREEN : RED;
        const cx = x + barW / 2;
        const isHovered = hovered === i;
        const tipW = 110;
        const tipH = d.note ? 34 : 24;
        const tipX = Math.min(Math.max(cx - tipW / 2, PAD.left), W - PAD.right - tipW);
        const tipY = Math.max(4, Math.min(bY, zeroY) - tipH - 6);
        const baseOpacity = d.dimmed ? 0.4 : 1;
        return (
          <g key={i} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}>
            <rect
              x={x}
              y={bY}
              width={barW}
              height={Math.max(1, bH)}
              fill={fill}
              opacity={hovered !== null && !isHovered ? baseOpacity * 0.3 : baseOpacity}
              rx={barW > 6 ? 2 : 0}
            />
            {i % labelEvery === 0 && (
              <text
                x={cx}
                y={H - PAD.bottom + 14}
                textAnchor={visible.length > 20 ? 'end' : 'middle'}
                fontSize={9}
                fill={TICKTXT}
                transform={visible.length > 20 ? `rotate(-45, ${cx}, ${H - PAD.bottom + 14})` : undefined}
              >
                {d.label}
              </text>
            )}
            {isHovered && (
              <g>
                <rect x={tipX} y={tipY} width={tipW} height={tipH} fill="#27272a" rx={4} stroke={AXIS} strokeWidth={1} />
                <text x={tipX + tipW / 2} y={tipY + 13} textAnchor="middle" fontSize={11} fill="#e4e4e7" fontWeight="500">
                  {fmtVal(v)}
                </text>
                <text x={tipX + tipW / 2} y={tipY + (d.note ? 25 : 25)} textAnchor="middle" fontSize={9} fill={TICKTXT}>
                  {d.note ? `${d.label} · ${d.note}` : d.label}
                </text>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export interface LinePoint {
  label: string;
  value: number; // e.g. drawdown percent (<= 0)
}

/** Area-to-zero line chart (drawdown). Fill red below zero. */
export function SvgLineChart({
  data,
  fmtVal,
  fmtTick,
  color = RED,
}: {
  data: LinePoint[];
  fmtVal: (v: number) => string;
  fmtTick: (v: number) => string;
  color?: string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  if (data.length === 0) return <Empty msg="No data" />;

  const values = data.map((d) => d.value);
  const minV = Math.min(0, ...values);
  const maxV = Math.max(0, ...values);
  const { toY } = yScale(minV, maxV);
  const zeroY = toY(0);
  const stepX = IW / Math.max(1, data.length - 1);
  const x = (i: number) => PAD.left + i * stepX;

  const line = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${toY(d.value)}`).join(' ');
  const area = `${line} L ${x(data.length - 1)} ${zeroY} L ${x(0)} ${zeroY} Z`;
  const labelEvery = Math.max(1, Math.ceil(data.length / 12));

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}>
      {gridlines(minV, maxV, toY, fmtTick)}
      <path d={area} fill={color} opacity={0.18} />
      <path d={line} fill="none" stroke={color} strokeWidth={1.5} />
      {data.map((d, i) =>
        i % labelEvery === 0 ? (
          <text key={`l${i}`} x={x(i)} y={H - PAD.bottom + 14} textAnchor="middle" fontSize={9} fill={TICKTXT}>
            {d.label}
          </text>
        ) : null,
      )}
      {data.map((d, i) => {
        const isHovered = hovered === i;
        const tipW = 110;
        const tipH = 24;
        const tipX = Math.min(Math.max(x(i) - tipW / 2, PAD.left), W - PAD.right - tipW);
        const tipY = Math.max(4, toY(d.value) - tipH - 6);
        return (
          <g key={`p${i}`} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}>
            <rect x={x(i) - stepX / 2} y={PAD.top} width={stepX} height={IH} fill="transparent" />
            {isHovered && (
              <>
                <circle cx={x(i)} cy={toY(d.value)} r={3} fill={color} />
                <rect x={tipX} y={tipY} width={tipW} height={tipH} fill="#27272a" rx={4} stroke={AXIS} strokeWidth={1} />
                <text x={tipX + tipW / 2} y={tipY + 10} textAnchor="middle" fontSize={11} fill="#e4e4e7" fontWeight="500">
                  {fmtVal(d.value)}
                </text>
                <text x={tipX + tipW / 2} y={tipY + 20} textAnchor="middle" fontSize={9} fill={TICKTXT}>
                  {d.label}
                </text>
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export interface GroupedDatum {
  label: string;
  a: number; // series A value
  b: number; // series B value
}

/** Two bars per category (e.g. long vs short, or ETF-leg vs basket-leg). */
export function SvgGroupedBar({
  data,
  aLabel,
  bLabel,
  fmtVal,
  fmtTick,
  aColor = GREEN,
  bColor = BLUE,
}: {
  data: GroupedDatum[];
  aLabel: string;
  bLabel: string;
  fmtVal: (v: number) => string;
  fmtTick: (v: number) => string;
  aColor?: string;
  bColor?: string;
}) {
  const [hovered, setHovered] = useState<{ i: number; s: 'a' | 'b' } | null>(null);
  if (data.length === 0) return <Empty msg="No data" />;

  const all = data.flatMap((d) => [d.a, d.b]);
  const minV = Math.min(0, ...all);
  const maxV = Math.max(0, ...all);
  const { toY } = yScale(minV, maxV);
  const zeroY = toY(0);
  const slotW = IW / data.length;
  const barW = (slotW * 0.72) / 2;
  const labelEvery = Math.max(1, Math.ceil(data.length / 12));

  const bar = (v: number, x: number, color: string, i: number, s: 'a' | 'b') => {
    const bH = Math.abs(toY(v) - zeroY);
    const bY = v >= 0 ? zeroY - bH : zeroY;
    const isH = hovered?.i === i && hovered?.s === s;
    const dim = hovered !== null && !isH ? 0.35 : 1;
    return <rect x={x} y={bY} width={barW} height={Math.max(1, bH)} fill={color} opacity={dim} rx={barW > 6 ? 2 : 0} onMouseEnter={() => setHovered({ i, s })} onMouseLeave={() => setHovered(null)} />;
  };

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}>
      {gridlines(minV, maxV, toY, fmtTick)}
      {data.map((d, i) => {
        const x0 = PAD.left + i * slotW + slotW * 0.14;
        const cx = x0 + barW;
        return (
          <g key={i}>
            {bar(d.a, x0, aColor, i, 'a')}
            {bar(d.b, x0 + barW, bColor, i, 'b')}
            {i % labelEvery === 0 && (
              <text x={cx} y={H - PAD.bottom + 14} textAnchor={data.length > 20 ? 'end' : 'middle'} fontSize={9} fill={TICKTXT} transform={data.length > 20 ? `rotate(-45, ${cx}, ${H - PAD.bottom + 14})` : undefined}>
                {d.label}
              </text>
            )}
          </g>
        );
      })}
      {hovered &&
        (() => {
          const d = data[hovered.i];
          const v = hovered.s === 'a' ? d.a : d.b;
          const name = hovered.s === 'a' ? aLabel : bLabel;
          const x0 = PAD.left + hovered.i * slotW + slotW * 0.14 + (hovered.s === 'b' ? barW : 0);
          const cx = x0 + barW / 2;
          const tipW = 120;
          const tipH = 34;
          const tipX = Math.min(Math.max(cx - tipW / 2, PAD.left), W - PAD.right - tipW);
          const tipY = Math.max(4, toY(v) - tipH - 6);
          return (
            <g>
              <rect x={tipX} y={tipY} width={tipW} height={tipH} fill="#27272a" rx={4} stroke={AXIS} strokeWidth={1} />
              <text x={tipX + tipW / 2} y={tipY + 13} textAnchor="middle" fontSize={11} fill="#e4e4e7" fontWeight="500">
                {fmtVal(v)}
              </text>
              <text x={tipX + tipW / 2} y={tipY + 25} textAnchor="middle" fontSize={9} fill={TICKTXT}>
                {d.label} · {name}
              </text>
            </g>
          );
        })()}
      {/* legend */}
      <g>
        <rect x={PAD.left} y={4} width={9} height={9} fill={aColor} rx={2} />
        <text x={PAD.left + 13} y={12} fontSize={10} fill={TICKTXT}>{aLabel}</text>
        <rect x={PAD.left + 70} y={4} width={9} height={9} fill={bColor} rx={2} />
        <text x={PAD.left + 83} y={12} fontSize={10} fill={TICKTXT}>{bLabel}</text>
      </g>
    </svg>
  );
}

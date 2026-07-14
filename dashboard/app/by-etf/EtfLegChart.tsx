'use client';

import { SvgGroupedBar, type GroupedDatum } from '../components/charts';

/**
 * Client wrapper for the per-ETF long-vs-short chart. The formatter props
 * (`fmtVal`/`fmtTick`) are functions and cannot be passed from the server
 * `by-etf/page.tsx` into the client `SvgGroupedBar` directly, so they are
 * defined here on the client side.
 */
export default function EtfLegChart({ data }: { data: GroupedDatum[] }) {
  return (
    <SvgGroupedBar
      data={data}
      aLabel="Long"
      bLabel="Short"
      fmtVal={(v) => `${v >= 0 ? '+' : '-'}$${Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
      fmtTick={(v) => `$${(v / 1000).toFixed(1)}k`}
    />
  );
}

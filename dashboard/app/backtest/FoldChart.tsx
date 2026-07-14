'use client';

import { SvgBarChart, type BarDatum } from '../components/charts';

/**
 * Client wrapper for the walk-forward fold chart — the formatter props are
 * functions and can't be passed from the server page into the client chart.
 */
export default function FoldChart({ data, kind }: { data: BarDatum[]; kind: 'sharpe' | 'ret' }) {
  const isRet = kind === 'ret';
  return (
    <SvgBarChart
      data={data}
      signed={false}
      fmtVal={(v) => (isRet ? `+${(v * 100).toFixed(1)}%` : v.toFixed(2))}
      fmtTick={(v) => (isRet ? `${(v * 100).toFixed(0)}%` : v.toFixed(1))}
    />
  );
}

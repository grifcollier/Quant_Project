import type { ReactNode } from 'react';

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-zinc-900 border border-zinc-800 rounded-xl p-5 ${className}`}>
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  positive,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
}) {
  const valueColor =
    positive === undefined
      ? 'text-zinc-100'
      : positive
        ? 'text-emerald-400'
        : 'text-red-400';
  return (
    <Card>
      <p className="text-zinc-500 text-xs uppercase tracking-wider mb-2">{label}</p>
      <p className={`text-2xl font-semibold tabular-nums ${valueColor}`}>{value}</p>
      {sub && <p className="text-zinc-500 text-xs mt-1">{sub}</p>}
    </Card>
  );
}

/** Open-position exposure split into long / short / net (short shown negative). */
export function ExposureCard({
  long,
  short,
  net,
  gross,
  leverage,
}: {
  long: number;
  short: number; // Alpaca convention: <= 0
  net: number;
  gross: number;
  leverage?: number;
}) {
  const Row = ({ label, value, cls, bold }: { label: string; value: string; cls: string; bold?: boolean }) => (
    <div className="flex items-baseline justify-between">
      <span className="text-zinc-500 text-xs">{label}</span>
      <span className={`tabular-nums ${bold ? 'text-base font-semibold' : 'text-sm'} ${cls}`}>{value}</span>
    </div>
  );
  return (
    <Card>
      <p className="text-zinc-500 text-xs uppercase tracking-wider mb-2">Open Exposure</p>
      <div className="space-y-1">
        <Row label="Long" value={fmt(long)} cls="text-emerald-400" />
        <Row label="Short" value={short < 0 ? fmtSigned(short) : fmt(0)} cls="text-blue-400" />
        <Row label="Net" value={fmtSigned(net)} cls={colorSigned(net)} bold />
      </div>
      <p className="text-zinc-500 text-xs mt-2">
        Gross {fmt(gross)}
        {leverage != null && Number.isFinite(leverage) ? ` · ${leverage.toFixed(2)}× lev` : ''}
      </p>
    </Card>
  );
}

export function Table({ headers, children }: { headers: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/60">
            {headers.map((h) => (
              <th key={h} className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Tr({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <tr className={`border-b border-zinc-800/60 last:border-0 hover:bg-zinc-800/30 transition-colors ${className}`}>
      {children}
    </tr>
  );
}

export function Td({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <td className={`px-4 py-3 text-zinc-300 whitespace-nowrap ${className}`}>
      {children}
    </td>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="bg-red-950/40 border border-red-800/60 rounded-lg px-4 py-3 text-red-300 text-sm">
      {message}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <p className="text-zinc-500 text-sm py-4">{message}</p>;
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-6">
      <h1 className="text-xl font-semibold text-zinc-100">{title}</h1>
      {children}
    </div>
  );
}

export function SignalBadge({ signal }: { signal: string }) {
  const map: Record<string, string> = {
    'LONG SPREAD':  'text-emerald-400 bg-emerald-400/10',
    'SHORT SPREAD': 'text-blue-400 bg-blue-400/10',
    'EXIT':         'text-yellow-400 bg-yellow-400/10',
    'STOP':         'text-red-400 bg-red-400/10',
    'HOLD':         'text-zinc-400 bg-zinc-400/10',
  };
  const cls = map[signal] ?? 'text-zinc-300 bg-zinc-300/10';
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {signal}
    </span>
  );
}

export function fmt(v: string | number, decimals = 2): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (isNaN(n)) return '—';
  return `$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

export function fmtPct(v: string | number, alreadyPercent = false): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (isNaN(n)) return '—';
  const pct = alreadyPercent ? n : n * 100;
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
}

export function fmtSigned(v: string | number): string {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (isNaN(n)) return '—';
  return `${n >= 0 ? '+' : '-'}$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function colorSigned(v: number): string {
  return v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-zinc-400';
}

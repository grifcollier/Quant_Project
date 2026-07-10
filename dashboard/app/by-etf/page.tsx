import { getActivities } from '@/lib/alpaca';
import { matchTrades, etfBreakdown } from '@/lib/trades';
import {
  PageHeader, Card, Table, Tr, Td, ErrorBanner, EmptyState, fmtSigned, colorSigned,
} from '../components/ui';
import { SvgGroupedBar } from '../components/charts';

export const dynamic = 'force-dynamic';

const PER_TRADE_TOOLTIP =
  'Per-trade return statistic (mean/std of this ETF’s closed-trade returns). NOT the daily-return, ' +
  '√252-annualized Sharpe on the Analytics tab — different methodology, not directly comparable.';

export default async function ByEtfPage() {
  let rows: ReturnType<typeof etfBreakdown> = [];
  let err = '';
  try {
    rows = etfBreakdown(matchTrades([...(await getActivities())].reverse()));
  } catch (e: unknown) {
    err = (e as Error).message;
  }

  const legData = rows.map((r) => ({ label: r.etf, a: r.longPl, b: r.shortPl }));

  return (
    <div className="space-y-8">
      <PageHeader title="By ETF">
        <a href="/by-etf" className="text-xs text-zinc-400 hover:text-zinc-200">Refresh</a>
      </PageHeader>
      {err && <ErrorBanner message={`Activities: ${err}`} />}

      {rows.length === 0 ? (
        <EmptyState message="No closed trades yet." />
      ) : (
        <>
          {/* Unmissable caveat: these Sharpe/Sortino are per-trade, not the account daily-return metric. */}
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-2 text-xs text-amber-300/90">
            <span className="font-medium text-amber-300">Note —</span> the{' '}
            <span className="text-amber-400">Sharpe / Sortino (per-trade)</span> columns are per-trade return ratios, computed
            differently from the daily-return, √252-annualized Sharpe on the <span className="text-zinc-300">Analytics</span> tab.
            They are <span className="text-amber-300">not directly comparable</span> across the two tabs.
          </div>

          <Table headers={['ETF', 'Realized P&L', 'Long P&L', 'Short P&L', 'Trades', 'Win Rate', 'Sharpe (per-trade)', 'Sortino (per-trade)']}>
            {rows.map((r) => (
              <Tr key={r.etf}>
                <Td><span className="font-medium text-zinc-100">{r.etf}</span></Td>
                <Td className={`tabular-nums ${colorSigned(r.realizedPl)}`}>{fmtSigned(r.realizedPl)}</Td>
                <Td className={`tabular-nums ${colorSigned(r.longPl)}`}>{fmtSigned(r.longPl)}</Td>
                <Td className={`tabular-nums ${colorSigned(r.shortPl)}`}>{fmtSigned(r.shortPl)}</Td>
                <Td className="tabular-nums">{r.tradeCount}</Td>
                <Td className="tabular-nums">{r.winRate.toFixed(0)}%</Td>
                <Td className="tabular-nums">
                  <span className="text-amber-400" title={PER_TRADE_TOOLTIP}>{r.tradeSharpe.toFixed(2)}</span>
                </Td>
                <Td className="tabular-nums">
                  <span className="text-amber-400" title={PER_TRADE_TOOLTIP}>{r.tradeSortino.toFixed(2)}</span>
                </Td>
              </Tr>
            ))}
          </Table>

          <Card>
            <h2 className="text-base font-medium text-zinc-300 mb-1">Realized P&amp;L by ETF — Long vs Short</h2>
            <SvgGroupedBar
              data={legData}
              aLabel="Long"
              bLabel="Short"
              fmtVal={(v) => `${v >= 0 ? '+' : '-'}$${Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
              fmtTick={(v) => `$${(v / 1000).toFixed(1)}k`}
            />
          </Card>
        </>
      )}
    </div>
  );
}

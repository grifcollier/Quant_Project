import { getActivities } from '@/lib/alpaca';
import { symbolRoundTrips, basketTrades, etfBreakdown } from '@/lib/trades';
import {
  PageHeader, Card, Table, Tr, Td, ErrorBanner, EmptyState, fmtSigned, colorSigned,
} from '../components/ui';
import EtfLegChart from './EtfLegChart';

export const dynamic = 'force-dynamic';

const PER_TRADE_TOOLTIP =
  'Per basket-trade return statistic (mean/std of this ETF’s completed basket-cycle returns). With only a ' +
  'handful of completed cycles per ETF this is very noisy. NOT the daily-return, √252-annualized Sharpe on ' +
  'the Analytics tab — different methodology, not directly comparable.';

export default async function ByEtfPage() {
  let rows: ReturnType<typeof etfBreakdown> = [];
  let err = '';
  try {
    rows = etfBreakdown(basketTrades(symbolRoundTrips([...(await getActivities())].reverse())));
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
          {/* Surface both caveats: what a "basket trade" is, and that these Sharpe/Sortino are per-trade. */}
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-2 text-xs text-amber-300/90">
            <span className="font-medium text-amber-300">Note —</span> a{' '}
            <span className="text-zinc-200">basket trade</span> is one full spread cycle for an ETF — every leg (the ETF plus its
            constituent stocks) entered and exited together counts as a <span className="text-zinc-200">single trade</span>, and only{' '}
            <span className="text-zinc-200">completed</span> cycles are counted (open positions are excluded until they close).
            The <span className="text-amber-400">Sharpe / Sortino (per-trade)</span> columns are per basket-trade return ratios —
            noisy over so few cycles and <span className="text-amber-300">not comparable</span> to the daily-return, √252 Sharpe on
            the <span className="text-zinc-300">Analytics</span> tab.
          </div>

          <Table headers={['ETF', 'Realized P&L', 'Long P&L', 'Short P&L', 'Basket Trades', 'Win Rate', 'Sharpe (per-trade)', 'Sortino (per-trade)']}>
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
            <EtfLegChart data={legData} />
          </Card>
        </>
      )}
    </div>
  );
}

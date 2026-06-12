import { getActivities } from '@/lib/alpaca';
import { matchTrades, type TradeRecord } from '@/lib/trades';
import {
  StatCard, Table, Tr, Td, ErrorBanner, EmptyState, PageHeader,
  fmt, fmtSigned, colorSigned,
} from '../components/ui';

export const dynamic = 'force-dynamic';

export default async function PnlPage() {
  let trades: TradeRecord[] = [], err = '';
  try {
    const activities = await getActivities();
    trades = matchTrades([...activities].reverse());
  } catch (e: unknown) {
    err = (e as Error).message;
  }

  const totalPl   = trades.reduce((s, t) => s + t.realizedPl, 0);
  const wins      = trades.filter(t => t.realizedPl > 0).length;
  const winRate   = trades.length > 0 ? (wins / trades.length) * 100 : 0;
  const avgReturn = trades.length > 0 ? trades.reduce((s, t) => s + t.returnPct, 0) / trades.length : 0;
  const avgHold   = trades.length > 0 ? trades.reduce((s, t) => s + t.holdDays, 0) / trades.length : 0;

  return (
    <div className="space-y-6">
      <PageHeader title="Realized P&L">
        <a href="/pnl" className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors">↻ Refresh</a>
      </PageHeader>

      {err && <ErrorBanner message={err} />}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard
          label="Total Realized P&L"
          value={fmtSigned(totalPl)}
          positive={totalPl >= 0}
        />
        <StatCard
          label="Win Rate"
          value={trades.length > 0 ? `${winRate.toFixed(1)}%` : '—'}
          sub={`${wins} wins / ${trades.length} trades`}
        />
        <StatCard
          label="Avg Return / Trade"
          value={trades.length > 0 ? `${avgReturn >= 0 ? '+' : ''}${avgReturn.toFixed(2)}%` : '—'}
          positive={trades.length > 0 ? avgReturn >= 0 : undefined}
        />
        <StatCard
          label="Avg Hold Days"
          value={trades.length > 0 ? avgHold.toFixed(1) : '—'}
        />
      </div>

      {trades.length === 0 ? (
        <EmptyState message={err ? '' : 'No closed trades yet — P&L will appear here once positions are opened and closed.'} />
      ) : (
        <Table headers={['Exit Date', 'Symbol', 'Side', 'Qty', 'Entry', 'Exit', 'Hold Days', 'Realized P&L', 'Return']}>
          {trades.map((t, i) => (
            <Tr key={i}>
              <Td className="text-zinc-400 text-xs">
                {new Date(t.exitDate).toLocaleDateString('en-US', {
                  month: 'short', day: 'numeric', year: '2-digit',
                })}
              </Td>
              <Td><span className="font-semibold text-zinc-100">{t.symbol}</span></Td>
              <Td>
                <span className={t.side === 'long' ? 'text-emerald-400' : 'text-blue-400'}>
                  {t.side.toUpperCase()}
                </span>
              </Td>
              <Td className="tabular-nums">{t.qty.toFixed(4)}</Td>
              <Td className="tabular-nums">{fmt(t.entryPrice)}</Td>
              <Td className="tabular-nums">{fmt(t.exitPrice)}</Td>
              <Td className="tabular-nums text-zinc-400">{t.holdDays}</Td>
              <Td className={`tabular-nums font-medium ${colorSigned(t.realizedPl)}`}>
                {fmtSigned(t.realizedPl)}
              </Td>
              <Td className={`tabular-nums ${colorSigned(t.returnPct)}`}>
                {`${t.returnPct >= 0 ? '+' : ''}${t.returnPct.toFixed(2)}%`}
              </Td>
            </Tr>
          ))}
        </Table>
      )}
    </div>
  );
}

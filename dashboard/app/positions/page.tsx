import { getAccount, getPositions, type AlpacaAccount, type AlpacaPosition } from '@/lib/alpaca';
import {
  StatCard, Table, Tr, Td, ErrorBanner, EmptyState, PageHeader,
  fmt, fmtPct, fmtSigned, colorSigned,
} from '../components/ui';

export const dynamic = 'force-dynamic';

export default async function PositionsPage() {
  let account: AlpacaAccount | null = null;
  let positions: AlpacaPosition[]   = [];
  let err = '';
  try {
    [account, positions] = await Promise.all([getAccount(), getPositions()]);
  } catch (e: unknown) {
    err = (e as Error).message;
  }

  const pos          = positions;
  const totalUpl     = pos.reduce((s, p) => s + parseFloat(p.unrealized_pl), 0);
  const totalMktVal  = pos.reduce((s, p) => s + parseFloat(p.market_value),  0);
  const totalCost    = pos.reduce((s, p) => s + parseFloat(p.cost_basis),    0);

  return (
    <div className="space-y-6">
      <PageHeader title="Open Positions">
        <a href="/positions" className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors">
          ↻ Refresh
        </a>
      </PageHeader>

      {err && <ErrorBanner message={err} />}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard
          label="Positions Open"
          value={String(pos.length)}
        />
        <StatCard
          label="Market Value"
          value={pos.length > 0 ? fmt(totalMktVal) : '—'}
          sub={pos.length > 0 ? `Cost basis ${fmt(totalCost)}` : undefined}
        />
        <StatCard
          label="Total Unrealized P&L"
          value={pos.length > 0 ? fmtSigned(totalUpl) : '—'}
          positive={pos.length > 0 ? totalUpl >= 0 : undefined}
        />
        <StatCard
          label="Buying Power"
          value={account ? fmt(account.buying_power) : '—'}
        />
      </div>

      {pos.length === 0 ? (
        <EmptyState message="No open positions." />
      ) : (
        <Table headers={['Symbol', 'Side', 'Qty', 'Avg Entry', 'Current Price', 'Market Value', 'Cost Basis', 'Unrealized P&L', 'Return']}>
          {pos.map((p) => {
            const upl = parseFloat(p.unrealized_pl);
            const uplPct = parseFloat(p.unrealized_plpc) * 100;
            return (
              <Tr key={p.symbol}>
                <Td><span className="font-semibold text-zinc-100">{p.symbol}</span></Td>
                <Td>
                  <span className={p.side === 'long' ? 'text-emerald-400' : 'text-blue-400'}>
                    {p.side.toUpperCase()}
                  </span>
                </Td>
                <Td className="tabular-nums">{parseFloat(p.qty).toFixed(4)}</Td>
                <Td className="tabular-nums">{fmt(p.avg_entry_price)}</Td>
                <Td className="tabular-nums">{fmt(p.current_price)}</Td>
                <Td className="tabular-nums">{fmt(p.market_value)}</Td>
                <Td className="tabular-nums">{fmt(p.cost_basis)}</Td>
                <Td className={`tabular-nums ${colorSigned(upl)}`}>
                  {fmtSigned(upl)}
                </Td>
                <Td className={`tabular-nums ${colorSigned(uplPct)}`}>
                  {`${uplPct >= 0 ? '+' : ''}${uplPct.toFixed(2)}%`}
                </Td>
              </Tr>
            );
          })}
        </Table>
      )}
    </div>
  );
}

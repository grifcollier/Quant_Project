import { getAccount, getPositions, type AlpacaPosition } from '@/lib/alpaca';
import {
  StatCard, ExposureCard, Table, Tr, Td, ErrorBanner, EmptyState,
  PageHeader, fmt, fmtPct, fmtSigned, colorSigned,
} from './components/ui';

export const dynamic = 'force-dynamic';

export default async function OverviewPage() {
  let account = null;
  let positions: AlpacaPosition[] = [];
  let accountErr = '';

  try { account   = await getAccount();   } catch (e: unknown) { accountErr = (e as Error).message; }
  try { positions = await getPositions(); } catch { /* shown via empty state */ }

  const equity     = account ? parseFloat(account.equity)      : null;
  const lastEquity = account ? parseFloat(account.last_equity) : null;
  const dailyPl    = equity != null && lastEquity != null ? equity - lastEquity : null;

  const longVal  = positions.filter(p => p.side === 'long').reduce((s, p) => s + parseFloat(p.market_value), 0);
  const shortVal = positions.filter(p => p.side === 'short').reduce((s, p) => s + parseFloat(p.market_value), 0); // <= 0
  const netVal   = longVal + shortVal;
  const grossVal = longVal + Math.abs(shortVal);
  const leverage = equity && equity > 0 ? grossVal / equity : undefined;

  return (
    <div className="space-y-8">
      <PageHeader title="Overview" />

      {accountErr && <ErrorBanner message={`Alpaca: ${accountErr}`} />}

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatCard label="Portfolio Equity" value={account ? fmt(account.equity) : '—'} />
        <StatCard label="Buying Power"     value={account ? fmt(account.buying_power) : '—'} />
        {positions.length > 0 ? (
          <ExposureCard long={longVal} short={shortVal} net={netVal} gross={grossVal} leverage={leverage} />
        ) : (
          <StatCard label="Open Exposure" value="—" />
        )}
        <StatCard
          label="Today's P&L"
          value={dailyPl != null ? fmtSigned(dailyPl) : '—'}
          positive={dailyPl != null ? dailyPl >= 0 : undefined}
        />
      </div>

      <section>
        <h2 className="text-base font-medium text-zinc-300 mb-3">
          Open Positions <span className="text-zinc-500 font-normal">({positions.length})</span>
        </h2>
        {positions.length === 0 ? (
          <EmptyState message="No open positions." />
        ) : (
          <Table headers={['Symbol', 'Qty', 'Market Value', 'Avg Entry', 'Current', 'Unrealized P&L']}>
            {positions.map((p) => {
              const upl = parseFloat(p.unrealized_pl);
              return (
                <Tr key={p.symbol}>
                  <Td><span className="font-medium text-zinc-100">{p.symbol}</span></Td>
                  <Td className="tabular-nums">{parseFloat(p.qty).toFixed(4)}</Td>
                  <Td className="tabular-nums">{fmt(p.market_value)}</Td>
                  <Td className="tabular-nums">{fmt(p.avg_entry_price)}</Td>
                  <Td className="tabular-nums">{fmt(p.current_price)}</Td>
                  <Td className={`tabular-nums ${colorSigned(upl)}`}>
                    {fmtSigned(upl)} ({fmtPct(p.unrealized_plpc)})
                  </Td>
                </Tr>
              );
            })}
          </Table>
        )}
      </section>
    </div>
  );
}

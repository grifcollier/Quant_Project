import { getOrders } from '@/lib/alpaca';
import {
  Table, Tr, Td, ErrorBanner, EmptyState, PageHeader, fmt,
} from '../components/ui';

export const dynamic = 'force-dynamic';

export default async function OrdersPage() {
  let orders = [], err = '';
  try { orders = await getOrders(); } catch (e: unknown) { err = (e as Error).message; }

  const filled = (orders as Awaited<ReturnType<typeof getOrders>>).filter(
    (o) => o.status === 'filled'
  );

  return (
    <div className="space-y-6">
      <PageHeader title="Order History">
        <div className="flex items-center gap-4">
          <span className="text-zinc-500 text-sm">{filled.length} filled orders</span>
          <a href="/orders" className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors">↻ Refresh</a>
        </div>
      </PageHeader>

      {err && <ErrorBanner message={err} />}

      {filled.length === 0 ? (
        <EmptyState message="No filled orders found." />
      ) : (
        <Table headers={['Filled At', 'Symbol', 'Side', 'Filled Qty', 'Avg Fill Price', 'Notional', 'Type', 'Status']}>
          {filled.map((o) => {
            const filledQty = parseFloat(o.filled_qty ?? '0');
            const fillPrice = o.filled_avg_price ? parseFloat(o.filled_avg_price) : null;
            const notional  = fillPrice ? filledQty * fillPrice : null;
            return (
              <Tr key={o.id}>
                <Td className="text-zinc-400 text-xs">
                  {o.filled_at ? new Date(o.filled_at).toLocaleString('en-US', {
                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                  }) : '—'}
                </Td>
                <Td><span className="font-semibold text-zinc-100">{o.symbol}</span></Td>
                <Td>
                  <span className={
                    o.side === 'buy' ? 'text-emerald-400' :
                    o.side === 'sell' ? 'text-red-400' :
                    o.side === 'sell_short' ? 'text-blue-400' :
                    'text-yellow-400'
                  }>
                    {o.side.replace('_', ' ').toUpperCase()}
                  </span>
                </Td>
                <Td className="tabular-nums">{filledQty.toFixed(4)}</Td>
                <Td className="tabular-nums">{fillPrice ? fmt(fillPrice) : '—'}</Td>
                <Td className="tabular-nums">{notional ? fmt(notional) : '—'}</Td>
                <Td className="text-zinc-500 text-xs">{o.type}</Td>
                <Td>
                  <span className="text-emerald-400 text-xs font-medium">{o.status}</span>
                </Td>
              </Tr>
            );
          })}
        </Table>
      )}
    </div>
  );
}

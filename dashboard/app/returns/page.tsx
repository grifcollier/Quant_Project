import { getActivities } from '@/lib/alpaca';
import { matchTrades, bucketTrades, type TradeRecord, type PeriodStats } from '@/lib/trades';
import { ErrorBanner, PageHeader } from '../components/ui';
import ReturnsClient from './ReturnsClient';

export const dynamic = 'force-dynamic';

export default async function ReturnsPage() {
  let daily:   PeriodStats[] = [];
  let weekly:  PeriodStats[] = [];
  let monthly: PeriodStats[] = [];
  let overall = { totalPl: 0, winRate: 0, avgReturn: 0, avgHoldDays: 0, tradeCount: 0 };
  let err = '';

  try {
    const activities = await getActivities();
    const trades: TradeRecord[] = matchTrades([...activities].reverse());

    daily   = bucketTrades(trades, 'daily');
    weekly  = bucketTrades(trades, 'weekly');
    monthly = bucketTrades(trades, 'monthly');

    if (trades.length > 0) {
      const wins = trades.filter(t => t.realizedPl > 0).length;
      overall = {
        totalPl:     trades.reduce((s, t) => s + t.realizedPl, 0),
        winRate:     (wins / trades.length) * 100,
        avgReturn:   trades.reduce((s, t) => s + t.returnPct, 0) / trades.length,
        avgHoldDays: trades.reduce((s, t) => s + t.holdDays, 0) / trades.length,
        tradeCount:  trades.length,
      };
    }
  } catch (e: unknown) {
    err = (e as Error).message;
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Returns Summary">
        <a href="/returns" className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors">↻ Refresh</a>
      </PageHeader>
      {err && <ErrorBanner message={err} />}
      <ReturnsClient daily={daily} weekly={weekly} monthly={monthly} overall={overall} />
    </div>
  );
}

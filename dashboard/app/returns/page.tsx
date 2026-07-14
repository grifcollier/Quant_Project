import { getActivities } from '@/lib/alpaca';
import {
  symbolRoundTrips, basketTrades, basketTradeRows, bucketBaskets,
  type BasketTrade, type TradeRow, type PeriodStats,
} from '@/lib/trades';
import { ErrorBanner, PageHeader } from '../components/ui';
import ReturnsClient from './ReturnsClient';

export const dynamic = 'force-dynamic';

export default async function ReturnsPage() {
  let trades:  TradeRow[]    = [];
  let weekly:  PeriodStats[] = [];
  let monthly: PeriodStats[] = [];
  let overall = { totalPl: 0, winRate: 0, avgReturn: 0, avgHoldDays: 0, tradeCount: 0 };
  let err = '';

  try {
    const activities = await getActivities();
    // One trade = one basket spread round-trip, the same unit the backtester and
    // the Analytics / By ETF tabs count. Every view below shares it, so the
    // per-trade rows always sum to the weekly and monthly bars.
    const baskets: BasketTrade[] = basketTrades(symbolRoundTrips([...activities].reverse()));

    trades  = basketTradeRows(baskets);
    weekly  = bucketBaskets(baskets, 'weekly');
    monthly = bucketBaskets(baskets, 'monthly');

    if (baskets.length > 0) {
      const wins = baskets.filter(b => b.realizedPl > 0).length;
      overall = {
        totalPl:     baskets.reduce((s, b) => s + b.realizedPl, 0),
        winRate:     (wins / baskets.length) * 100,
        avgReturn:   baskets.reduce((s, b) => s + b.returnPct, 0) / baskets.length,
        avgHoldDays: baskets.reduce((s, b) => s + b.holdDays, 0) / baskets.length,
        tradeCount:  baskets.length,
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
      <ReturnsClient trades={trades} weekly={weekly} monthly={monthly} overall={overall} />
    </div>
  );
}

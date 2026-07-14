import { getPortfolioHistory, getActivities } from '@/lib/alpaca';
import { symbolRoundTrips, basketTrades, tradeSummary, legBreakdown, type LegPeriod, type TradeSummary } from '@/lib/trades';
import {
  pctChange, sharpe, sortino, maxDrawdown, currentDrawdown, totalReturn, cagr, calmar,
  monthlyMetrics, drawdownSeries, type MonthlyMetric, type DrawdownPoint,
} from '@/lib/analytics';
import { PageHeader, ErrorBanner } from '../components/ui';
import AnalyticsClient from './AnalyticsClient';

export const dynamic = 'force-dynamic';

export default async function AnalyticsPage() {
  let ts: number[] = [];
  let eq: number[] = [];
  let phErr = '';
  try {
    const ph = await getPortfolioHistory('all', '1D');
    const pairs = ph.timestamp
      .map((t, i) => [t, ph.equity[i]] as const)
      .filter(([, e]) => e != null && Number.isFinite(e) && (e as number) > 0);
    ts = pairs.map((p) => p[0]);
    eq = pairs.map((p) => p[1] as number);
  } catch (e: unknown) {
    phErr = (e as Error).message;
  }

  const returns = pctChange(eq);
  const maxDD = maxDrawdown(eq);
  const cagrVal = cagr(eq);
  const overall = {
    sharpe: sharpe(returns),
    sortino: sortino(returns),
    maxDD,
    curDD: currentDrawdown(eq),
    totalRet: totalReturn(eq),
    cagr: cagrVal,
    calmar: calmar(cagrVal, maxDD),
  };
  const monthly: MonthlyMetric[] = monthlyMetrics(ts, eq);
  const drawdown: DrawdownPoint[] = drawdownSeries(ts, eq);

  let summary: TradeSummary = { tradeCount: 0, winRate: 0, profitFactor: null, avgHoldDays: 0, bestReturn: 0, worstReturn: 0, avgWin: 0, avgLoss: 0 };
  let legs: LegPeriod[] = [];
  let tradesErr = '';
  try {
    const rts = symbolRoundTrips([...(await getActivities())].reverse());
    summary = tradeSummary(basketTrades(rts));
    legs = legBreakdown(rts).periods;
  } catch (e: unknown) {
    tradesErr = (e as Error).message;
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Analytics">
        <a href="/analytics" className="text-xs text-zinc-400 hover:text-zinc-200">Refresh</a>
      </PageHeader>
      {phErr && <ErrorBanner message={`Portfolio history: ${phErr}`} />}
      {tradesErr && <ErrorBanner message={`Activities: ${tradesErr}`} />}
      <AnalyticsClient
        overall={overall}
        monthly={monthly}
        drawdown={drawdown}
        legs={legs}
        summary={summary}
        hasEquity={eq.length > 1}
      />
    </div>
  );
}

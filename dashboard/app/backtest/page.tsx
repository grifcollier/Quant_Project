import { getPortfolioHistory, getActivities } from '@/lib/alpaca';
import { symbolRoundTrips, basketTrades, tradeSummary } from '@/lib/trades';
import {
  pctChange, sharpe, sortino, maxDrawdown, totalReturn, cagr,
} from '@/lib/analytics';
import { BACKTEST, BACKTEST_META, type BacktestPeriod } from '@/lib/backtest_reference';
import {
  PageHeader, Card, Table, Tr, Td, StatCard, ErrorBanner, fmtPct, colorSigned,
} from '../components/ui';
import FoldChart from './FoldChart';

export const dynamic = 'force-dynamic';

const pct = (v: number) => fmtPct(v);
const ddStr = (v: number) => `${(v * 100).toFixed(2)}%`;

export default async function BacktestPage() {
  // ── Live paper metrics (same formulas as the backtester / Analytics tab) ──
  let live = { sharpe: 0, sortino: 0, maxDD: 0, totalRet: 0, cagr: 0, hasEquity: false };
  let phErr = '';
  try {
    const ph = await getPortfolioHistory('all', '1D');
    const eq = ph.timestamp
      .map((_, i) => ph.equity[i])
      .filter((e): e is number => e != null && Number.isFinite(e) && (e as number) > 0);
    const r = pctChange(eq);
    live = {
      sharpe: sharpe(r), sortino: sortino(r), maxDD: maxDrawdown(eq),
      totalRet: totalReturn(eq), cagr: cagr(eq), hasEquity: eq.length > 1,
    };
  } catch (e: unknown) {
    phErr = (e as Error).message;
  }

  let summary = { tradeCount: 0, winRate: 0, profitFactor: null as number | null, avgHoldDays: 0 };
  let tradesErr = '';
  try {
    const s = tradeSummary(basketTrades(symbolRoundTrips([...(await getActivities())].reverse())));
    summary = { tradeCount: s.tradeCount, winRate: s.winRate, profitFactor: s.profitFactor, avgHoldDays: s.avgHoldDays };
  } catch (e: unknown) {
    tradesErr = (e as Error).message;
  }

  const bt5 = BACKTEST['5y'];
  const bt10 = BACKTEST['10y'];
  const dash = (v: string) => (live.hasEquity ? v : '—');

  return (
    <div className="space-y-8">
      <PageHeader title="Backtest">
        <a href="/backtest" className="text-xs text-zinc-400 hover:text-zinc-200">Refresh</a>
      </PageHeader>
      {phErr && <ErrorBanner message={`Portfolio history: ${phErr}`} />}
      {tradesErr && <ErrorBanner message={`Activities: ${tradesErr}`} />}

      <p className="text-sm text-zinc-400 leading-relaxed">
        Backtester reference vs live paper trading. Numbers use the{' '}
        <span className="text-zinc-200">same formulas</span> (daily-equity Sharpe √252, ddof=1; one trade = one basket
        spread round-trip). The backtest is the combined 5-ETF portfolio, ${(BACKTEST_META.capital / 1000).toFixed(0)}k
        capital ({BACKTEST_META.costBps}bps costs); the live account is now sized the same way ($20k/ETF).
      </p>

      {/* ── Comparability note ─────────────────────────────────────────────── */}
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-2 text-xs text-amber-300/90">
        <span className="font-medium text-amber-300">How to read this —</span>{' '}
        <span className="text-amber-400">Sharpe</span> is scale-invariant, so it&apos;s the cleanest apples-to-apples
        comparison. <span className="text-zinc-200">Total Return / Max Drawdown</span> depend on horizon and how fully
        the account is deployed — the backtest spans {bt5.years}–{bt10.years} years fully invested, while the live
        account is only a few weeks in and often holds idle cash when fewer than 5 ETFs have signals. Expect the live
        magnitudes to converge toward the backtest over time, not match today.
      </div>

      {/* ── Portfolio: backtest vs live ────────────────────────────────────── */}
      <Card>
        <h2 className="text-base font-medium text-zinc-300 mb-3">Combined portfolio — backtest vs live</h2>
        <Table headers={['Metric', 'Backtest · 5y', 'Backtest · 10y', 'Live paper · to date']}>
          <Tr className="bg-emerald-500/5">
            <Td><span className="font-medium text-zinc-100">Sharpe</span> <span className="text-emerald-400/80 text-xs">· comparable</span></Td>
            <Td className="tabular-nums">{bt5.sharpe.toFixed(2)}</Td>
            <Td className="tabular-nums">{bt10.sharpe.toFixed(2)}</Td>
            <Td className="tabular-nums text-emerald-300">{dash(live.sharpe.toFixed(2))}</Td>
          </Tr>
          <Tr>
            <Td><span className="font-medium text-zinc-100">Total Return</span> <span className="text-zinc-500 text-xs">· horizon-dependent</span></Td>
            <Td className={`tabular-nums ${colorSigned(bt5.totalReturn)}`}>{pct(bt5.totalReturn)}</Td>
            <Td className={`tabular-nums ${colorSigned(bt10.totalReturn)}`}>{pct(bt10.totalReturn)}</Td>
            <Td className={`tabular-nums ${colorSigned(live.totalRet)}`}>{dash(pct(live.totalRet))}</Td>
          </Tr>
          <Tr>
            <Td><span className="font-medium text-zinc-100">Max Drawdown</span> <span className="text-zinc-500 text-xs">· horizon-dependent</span></Td>
            <Td className="tabular-nums text-red-400">{ddStr(bt5.maxDrawdown)}</Td>
            <Td className="tabular-nums text-red-400">{ddStr(bt10.maxDrawdown)}</Td>
            <Td className="tabular-nums text-red-400">{dash(ddStr(live.maxDD))}</Td>
          </Tr>
        </Table>
        <p className="text-zinc-500 text-xs mt-3">
          Live paper (same method): Sortino {dash(live.sortino.toFixed(2))} · CAGR {dash(pct(live.cagr))} ·
          {' '}Win rate {summary.tradeCount ? `${summary.winRate.toFixed(0)}%` : '—'} ·
          {' '}Profit factor {summary.profitFactor != null ? summary.profitFactor.toFixed(2) : summary.tradeCount ? '∞' : '—'} ·
          {' '}{summary.tradeCount} basket trades · Avg hold {summary.tradeCount ? `${summary.avgHoldDays.toFixed(1)}d` : '—'}.
        </p>
      </Card>

      {/* ── Walk-forward (rolling window) ──────────────────────────────────── */}
      {([bt10, bt5] as BacktestPeriod[]).map((p) => (
        <Card key={p.key}>
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="text-base font-medium text-zinc-300">
              Walk-forward validation — {p.label}
            </h2>
            <span className="text-xs text-zinc-500">
              stitched OOS return <span className="text-emerald-300">{pct(p.oosReturn)}</span> · {p.oosLabel}
            </span>
          </div>
          <p className="text-zinc-500 text-xs mb-3">
            Rolling non-overlapping out-of-sample folds, no parameter re-fitting — each bar is one fold&apos;s Sharpe.
          </p>
          <FoldChart data={p.folds.map((f) => ({ label: f.label, value: f.sharpe, note: `${(f.ret * 100).toFixed(1)}% ret` }))} kind="sharpe" />
          <div className="mt-3">
            <Table headers={['Fold', 'Return', 'Sharpe']}>
              {p.folds.map((f) => (
                <Tr key={f.label}>
                  <Td>{f.label}</Td>
                  <Td className={`tabular-nums ${colorSigned(f.ret)}`}>{pct(f.ret)}</Td>
                  <Td className="tabular-nums">{f.sharpe.toFixed(2)}</Td>
                </Tr>
              ))}
            </Table>
          </div>
        </Card>
      ))}

      {/* ── Monte Carlo ────────────────────────────────────────────────────── */}
      <Card>
        <h2 className="text-base font-medium text-zinc-300 mb-1">Monte Carlo — 10k bootstrap sims</h2>
        <p className="text-zinc-500 text-xs mb-4">
          Resampling the daily-return stream with replacement — distribution of total return across orderings.
        </p>
        <div className="space-y-4">
          {([bt5, bt10] as BacktestPeriod[]).map((p) => (
            <div key={p.key}>
              <p className="text-xs text-zinc-400 mb-2">{p.label}</p>
              <div className="grid grid-cols-3 gap-4">
                <StatCard label="5th percentile" value={pct(p.monteCarlo.p5)} positive />
                <StatCard label="Median" value={pct(p.monteCarlo.median)} positive />
                <StatCard label="95th percentile" value={pct(p.monteCarlo.p95)} positive />
              </div>
            </div>
          ))}
        </div>
      </Card>

      <p className="text-zinc-600 text-xs">
        Backtest figures are precomputed offline (the dashboard can&apos;t run the Python backtest live). Regenerate with{' '}
        <code className="text-zinc-400">{BACKTEST_META.regenerate}</code> and update{' '}
        <code className="text-zinc-400">lib/backtest_reference.ts</code> when the strategy or data window changes.
      </p>
    </div>
  );
}

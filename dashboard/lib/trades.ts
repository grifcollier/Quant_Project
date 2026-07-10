import type { AlpacaActivity } from './alpaca';
import { mean, sampleStd } from './analytics';
import symbolEtfMap from './symbol_etf_map.json';

export interface TradeRecord {
  symbol: string;
  entryDate: string;
  exitDate: string;
  side: 'long' | 'short';
  entryPrice: number;
  exitPrice: number;
  qty: number;
  realizedPl: number;
  returnPct: number;
  holdDays: number;
}

export interface PeriodStats {
  key: string;
  label: string;
  realizedPl: number;
  winRate: number;
  avgReturn: number;
  avgHoldDays: number;
  tradeCount: number;
}

interface Lot { price: number; qty: number; date: string }

export function matchTrades(fills: AlpacaActivity[]): TradeRecord[] {
  const longLots:  Record<string, Lot[]> = {};
  const shortLots: Record<string, Lot[]> = {};
  const trades: TradeRecord[] = [];

  for (const fill of fills) {
    const { symbol, side, transaction_time: date } = fill;
    const qty   = parseFloat(fill.qty);
    const price = parseFloat(fill.price);
    if (!longLots[symbol])  longLots[symbol]  = [];
    if (!shortLots[symbol]) shortLots[symbol] = [];

    if (side === 'buy') {
      if (shortLots[symbol].length > 0) {
        let rem = qty;
        while (rem > 0 && shortLots[symbol].length > 0) {
          const lot = shortLots[symbol][0];
          const m = Math.min(rem, lot.qty);
          trades.push({
            symbol, side: 'short',
            entryDate: lot.date, exitDate: date,
            entryPrice: lot.price, exitPrice: price, qty: m,
            realizedPl: (lot.price - price) * m,
            returnPct: (lot.price / price - 1) * 100,
            holdDays: Math.round((new Date(date).getTime() - new Date(lot.date).getTime()) / 86_400_000),
          });
          lot.qty -= m; rem -= m;
          if (lot.qty <= 0) shortLots[symbol].shift();
        }
      } else {
        longLots[symbol].push({ price, qty, date });
      }
    } else if (side === 'sell') {
      if (longLots[symbol].length > 0) {
        let rem = qty;
        while (rem > 0 && longLots[symbol].length > 0) {
          const lot = longLots[symbol][0];
          const m = Math.min(rem, lot.qty);
          trades.push({
            symbol, side: 'long',
            entryDate: lot.date, exitDate: date,
            entryPrice: lot.price, exitPrice: price, qty: m,
            realizedPl: (price - lot.price) * m,
            returnPct: (price / lot.price - 1) * 100,
            holdDays: Math.round((new Date(date).getTime() - new Date(lot.date).getTime()) / 86_400_000),
          });
          lot.qty -= m; rem -= m;
          if (lot.qty <= 0) longLots[symbol].shift();
        }
      } else {
        shortLots[symbol].push({ price, qty, date });
      }
    }
  }

  return trades.sort((a, b) => new Date(b.exitDate).getTime() - new Date(a.exitDate).getTime());
}

function weekStart(date: Date): string {
  const d = new Date(date);
  const day = d.getDay();
  d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
  return d.toISOString().slice(0, 10);
}

function formatLabel(key: string, granularity: 'daily' | 'weekly' | 'monthly'): string {
  if (granularity === 'monthly') {
    const [y, m] = key.split('-');
    return new Date(parseInt(y), parseInt(m) - 1)
      .toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
  }
  return new Date(key + 'T12:00:00')
    .toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ---------------------------------------------------------------------------
// ETF / leg attribution (static symbol->ETF map from scripts/gen_symbol_etf_map.py)
// ---------------------------------------------------------------------------
export const ETF_TICKERS = ['XLK', 'XLF', 'XLV', 'XLI', 'XLE'] as const;
const ETF_SET = new Set<string>(ETF_TICKERS);
const SYMBOL_ETF = symbolEtfMap as Record<string, string>;

/** Map a fill/position symbol to its sector ETF, or 'Other' if unmapped. */
export function symbolToEtf(symbol: string): string {
  return SYMBOL_ETF[symbol] ?? 'Other';
}

/** Which leg of the spread a symbol belongs to: the ETF ticker vs a basket stock. */
export function symbolLeg(symbol: string): 'etf' | 'basket' {
  return ETF_SET.has(symbol) ? 'etf' : 'basket';
}

export interface EtfStats {
  etf: string;
  realizedPl: number;
  longPl: number;
  shortPl: number;
  tradeCount: number;
  winRate: number; // percent
  avgReturn: number; // mean per-trade returnPct
  // NOTE: per-trade ratios (mean/std of trade returns), NOT the daily-return,
  // sqrt(252)-annualized Sharpe on the Analytics tab. Different methodology,
  // not directly comparable — the UI labels these "(per-trade)".
  tradeSharpe: number;
  tradeSortino: number;
}

/** Un-annualized mean/std ratio of a per-trade return series. */
function tradeRatio(returns: number[], downsideOnly: boolean): number {
  const denom = sampleStd(downsideOnly ? returns.filter((r) => r < 0) : returns);
  if (returns.length < 2 || denom <= 0) return 0;
  return mean(returns) / denom;
}

export function etfBreakdown(trades: TradeRecord[]): EtfStats[] {
  const groups: Record<string, TradeRecord[]> = {};
  for (const t of trades) (groups[symbolToEtf(t.symbol)] ??= []).push(t);

  return Object.entries(groups)
    .map(([etf, ts]) => {
      const rets = ts.map((t) => t.returnPct);
      const wins = ts.filter((t) => t.realizedPl > 0).length;
      return {
        etf,
        realizedPl: ts.reduce((s, t) => s + t.realizedPl, 0),
        longPl: ts.filter((t) => t.side === 'long').reduce((s, t) => s + t.realizedPl, 0),
        shortPl: ts.filter((t) => t.side === 'short').reduce((s, t) => s + t.realizedPl, 0),
        tradeCount: ts.length,
        winRate: (wins / ts.length) * 100,
        avgReturn: mean(rets),
        tradeSharpe: tradeRatio(rets, false),
        tradeSortino: tradeRatio(rets, true),
      };
    })
    .sort((a, b) => b.realizedPl - a.realizedPl);
}

export interface LegPeriod {
  key: string;
  label: string;
  etfPl: number;
  basketPl: number;
}

/** ETF-leg vs basket-leg realized P&L, bucketed by month (+ overall totals). */
export function legBreakdown(trades: TradeRecord[]): {
  periods: LegPeriod[];
  totalEtf: number;
  totalBasket: number;
} {
  const map: Record<string, { etf: number; basket: number }> = {};
  let totalEtf = 0;
  let totalBasket = 0;
  for (const t of trades) {
    const key = t.exitDate.slice(0, 7);
    const bucket = (map[key] ??= { etf: 0, basket: 0 });
    if (symbolLeg(t.symbol) === 'etf') {
      bucket.etf += t.realizedPl;
      totalEtf += t.realizedPl;
    } else {
      bucket.basket += t.realizedPl;
      totalBasket += t.realizedPl;
    }
  }
  const periods = Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, v]) => ({ key, label: formatLabel(key, 'monthly'), etfPl: v.etf, basketPl: v.basket }));
  return { periods, totalEtf, totalBasket };
}

export interface TradeSummary {
  tradeCount: number;
  winRate: number;
  profitFactor: number | null; // null when undefined (no losses, or no wins)
  avgHoldDays: number;
  bestReturn: number;
  worstReturn: number;
}

/** Overall realized-trade summary (win rate / profit factor / hold), mirrors metrics.py. */
export function tradeSummary(trades: TradeRecord[]): TradeSummary {
  if (trades.length === 0) {
    return { tradeCount: 0, winRate: 0, profitFactor: null, avgHoldDays: 0, bestReturn: 0, worstReturn: 0 };
  }
  const wins = trades.filter((t) => t.realizedPl > 0);
  const losses = trades.filter((t) => t.realizedPl <= 0);
  const lossSum = losses.reduce((s, t) => s + t.realizedPl, 0);
  const rets = trades.map((t) => t.returnPct);
  return {
    tradeCount: trades.length,
    winRate: (wins.length / trades.length) * 100,
    profitFactor:
      wins.length && losses.length && lossSum !== 0
        ? wins.reduce((s, t) => s + t.realizedPl, 0) / Math.abs(lossSum)
        : null,
    avgHoldDays: mean(trades.map((t) => t.holdDays)),
    bestReturn: Math.max(...rets),
    worstReturn: Math.min(...rets),
  };
}

export function bucketTrades(trades: TradeRecord[], granularity: 'daily' | 'weekly' | 'monthly'): PeriodStats[] {
  const map: Record<string, TradeRecord[]> = {};
  for (const t of trades) {
    const key = granularity === 'daily'
      ? t.exitDate.slice(0, 10)
      : granularity === 'weekly'
        ? weekStart(new Date(t.exitDate))
        : t.exitDate.slice(0, 7);
    if (!map[key]) map[key] = [];
    map[key].push(t);
  }
  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, ts]) => {
      const wins = ts.filter(t => t.realizedPl > 0).length;
      return {
        key,
        label:       formatLabel(key, granularity),
        realizedPl:  ts.reduce((s, t) => s + t.realizedPl, 0),
        winRate:     (wins / ts.length) * 100,
        avgReturn:   ts.reduce((s, t) => s + t.returnPct, 0) / ts.length,
        avgHoldDays: ts.reduce((s, t) => s + t.holdDays, 0) / ts.length,
        tradeCount:  ts.length,
      };
    });
}

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
    } else if (side === 'sell' || side === 'sell_short') {
      // Alpaca reports short *opens* as `sell_short` and long *reductions* as
      // `sell`. Both are handled here: close any open long lots FIFO first, and
      // any remainder opens (or adds to) a short lot. Dropping `sell_short`
      // would silently lose every short leg and mis-book the covering buys.
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

function formatLabel(key: string, granularity: 'weekly' | 'monthly'): string {
  if (granularity === 'monthly') {
    const [y, m] = key.split('-');
    return new Date(parseInt(y), parseInt(m) - 1)
      .toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
  }
  return new Date(key + 'T12:00:00')
    .toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

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

// ---------------------------------------------------------------------------
// Completed round-trips & basket trades
//
// The raw fills produce many partial-fill lot matches (matchTrades). For the
// "how many trades" view we collapse those two levels:
//   1. symbolRoundTrips — one completed round-trip per symbol: the position
//      goes flat -> open -> flat, however many fills that took, counts once.
//      P&L = sell proceeds - buy cost over the cycle (exact, since it ends flat).
//   2. basketTrades — every symbol round-trip of the SAME ETF sharing the same
//      enter day and exit day is one basket trade (the whole spread cycle).
// Positions still open (never returned to flat) are excluded — they aren't a
// completed trade yet — so basket P&L can trail the lot-level realized P&L on
// the P&L tab by whatever the open positions have realized so far.
// ---------------------------------------------------------------------------
export interface SymRoundTrip {
  symbol: string;
  etf: string;
  direction: 'long' | 'short';
  entryDate: string;
  exitDate: string;
  realizedPl: number;
  notional: number; // capital deployed at entry (buy cost if long, sell proceeds if short)
}

const FLAT_TOL = 1e-6; // treat |net position| below this as flat (fractional-share drift)

/** Collapse chronological fills into one completed round-trip per symbol cycle. */
export function symbolRoundTrips(fills: AlpacaActivity[]): SymRoundTrip[] {
  const pos: Record<string, number> = {};
  const cur: Record<string, { entryDate: string; exitDate: string; dir: 'long' | 'short'; buy: number; sell: number }> = {};
  const out: SymRoundTrip[] = [];

  for (const f of fills) {
    const sym = f.symbol;
    const qty = parseFloat(f.qty);
    const price = parseFloat(f.price);
    const signed = f.side === 'buy' ? qty : -qty;

    let c = cur[sym];
    if (!c) {
      c = { entryDate: f.transaction_time, exitDate: f.transaction_time, dir: signed > 0 ? 'long' : 'short', buy: 0, sell: 0 };
      cur[sym] = c;
    }
    c.exitDate = f.transaction_time;
    if (f.side === 'buy') c.buy += qty * price;
    else c.sell += qty * price;

    pos[sym] = (pos[sym] ?? 0) + signed;
    if (Math.abs(pos[sym]) < FLAT_TOL) {
      out.push({
        symbol: sym,
        etf: symbolToEtf(sym),
        direction: c.dir,
        entryDate: c.entryDate,
        exitDate: c.exitDate,
        realizedPl: c.sell - c.buy,
        notional: c.dir === 'long' ? c.buy : c.sell,
      });
      delete cur[sym];
    }
  }
  return out;
}

export interface BasketTrade {
  etf: string;
  entryDate: string;
  exitDate: string;
  holdDays: number;
  legCount: number;
  realizedPl: number;
  returnPct: number; // basket P&L / capital deployed
  longPl: number;
  shortPl: number;
}

/** Group same-ETF, same enter-day/exit-day round-trips into one basket trade. */
export function basketTrades(rts: SymRoundTrip[]): BasketTrade[] {
  const groups: Record<string, SymRoundTrip[]> = {};
  for (const r of rts) {
    const key = `${r.etf}|${r.entryDate.slice(0, 10)}|${r.exitDate.slice(0, 10)}`;
    (groups[key] ??= []).push(r);
  }
  return Object.values(groups)
    .map((legs) => {
      const realizedPl = legs.reduce((s, l) => s + l.realizedPl, 0);
      const notional = legs.reduce((s, l) => s + l.notional, 0);
      const entryDate = legs.reduce((m, l) => (l.entryDate < m ? l.entryDate : m), legs[0].entryDate);
      const exitDate = legs.reduce((m, l) => (l.exitDate > m ? l.exitDate : m), legs[0].exitDate);
      return {
        etf: legs[0].etf,
        entryDate,
        exitDate,
        holdDays: Math.round((new Date(exitDate).getTime() - new Date(entryDate).getTime()) / 86_400_000),
        legCount: legs.length,
        realizedPl,
        returnPct: notional > 0 ? (realizedPl / notional) * 100 : 0,
        longPl: legs.filter((l) => l.direction === 'long').reduce((s, l) => s + l.realizedPl, 0),
        shortPl: legs.filter((l) => l.direction === 'short').reduce((s, l) => s + l.realizedPl, 0),
      };
    })
    .sort((a, b) => new Date(b.exitDate).getTime() - new Date(a.exitDate).getTime());
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

export function etfBreakdown(baskets: BasketTrade[]): EtfStats[] {
  const groups: Record<string, BasketTrade[]> = {};
  for (const b of baskets) (groups[b.etf] ??= []).push(b);

  return Object.entries(groups)
    .map(([etf, bs]) => {
      const rets = bs.map((b) => b.returnPct);
      const wins = bs.filter((b) => b.realizedPl > 0).length;
      return {
        etf,
        realizedPl: bs.reduce((s, b) => s + b.realizedPl, 0),
        longPl: bs.reduce((s, b) => s + b.longPl, 0),
        shortPl: bs.reduce((s, b) => s + b.shortPl, 0),
        tradeCount: bs.length,
        winRate: (wins / bs.length) * 100,
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
export function legBreakdown(rts: SymRoundTrip[]): {
  periods: LegPeriod[];
  totalEtf: number;
  totalBasket: number;
} {
  const map: Record<string, { etf: number; basket: number }> = {};
  let totalEtf = 0;
  let totalBasket = 0;
  for (const r of rts) {
    const key = r.exitDate.slice(0, 7);
    const bucket = (map[key] ??= { etf: 0, basket: 0 });
    if (symbolLeg(r.symbol) === 'etf') {
      bucket.etf += r.realizedPl;
      totalEtf += r.realizedPl;
    } else {
      bucket.basket += r.realizedPl;
      totalBasket += r.realizedPl;
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
  avgWin: number;  // mean $ P&L of winning basket trades (compute_metrics avg_win)
  avgLoss: number; // mean $ P&L of losing basket trades (<=0), compute_metrics avg_loss
}

/** Overall basket-trade summary (win rate / profit factor / hold), mirrors compute_metrics. */
export function tradeSummary(baskets: BasketTrade[]): TradeSummary {
  if (baskets.length === 0) {
    return { tradeCount: 0, winRate: 0, profitFactor: null, avgHoldDays: 0, bestReturn: 0, worstReturn: 0, avgWin: 0, avgLoss: 0 };
  }
  const wins = baskets.filter((b) => b.realizedPl > 0);
  const losses = baskets.filter((b) => b.realizedPl <= 0);
  const lossSum = losses.reduce((s, b) => s + b.realizedPl, 0);
  const rets = baskets.map((b) => b.returnPct);
  return {
    tradeCount: baskets.length,
    winRate: (wins.length / baskets.length) * 100,
    profitFactor:
      wins.length && losses.length && lossSum !== 0
        ? wins.reduce((s, b) => s + b.realizedPl, 0) / Math.abs(lossSum)
        : null,
    avgHoldDays: mean(baskets.map((b) => b.holdDays)),
    bestReturn: Math.max(...rets),
    worstReturn: Math.min(...rets),
    avgWin: wins.length ? mean(wins.map((b) => b.realizedPl)) : 0,
    avgLoss: losses.length ? mean(losses.map((b) => b.realizedPl)) : 0,
  };
}

/**
 * One basket round-trip per row, shaped like PeriodStats so the Returns tab can
 * render individual trades through the same chart/table as the calendar buckets.
 * Ascending by exit date, matching bucketBaskets.
 */
export interface TradeRow extends PeriodStats {
  etf: string;
  legCount: number;
}

export function basketTradeRows(baskets: BasketTrade[]): TradeRow[] {
  return [...baskets]
    .sort((a, b) => a.exitDate.localeCompare(b.exitDate))
    .map((b) => ({
      // Exit date first so the Returns tab's timeframe filter can compare keys
      // lexicographically as dates; ETF + entry date make it unique per trade.
      key: `${b.exitDate.slice(0, 10)}|${b.etf}|${b.entryDate.slice(0, 10)}`,
      label: `${b.etf} ${shortDate(b.entryDate)}→${shortDate(b.exitDate)}`,
      realizedPl: b.realizedPl,
      winRate: b.realizedPl > 0 ? 100 : 0, // binary for a single trade; UI shows Win/Loss
      avgReturn: b.returnPct,
      avgHoldDays: b.holdDays,
      tradeCount: 1,
      etf: b.etf,
      legCount: b.legCount,
    }));
}

/**
 * Bucket basket trades by exit week/month. Same PeriodStats shape as the rows
 * above, so every Returns view counts one trade the same way the backtester and
 * the Analytics/By-ETF tabs do: one basket spread round-trip, not one lot match.
 */
export function bucketBaskets(baskets: BasketTrade[], granularity: 'weekly' | 'monthly'): PeriodStats[] {
  const map: Record<string, BasketTrade[]> = {};
  for (const b of baskets) {
    const key = granularity === 'weekly' ? weekStart(new Date(b.exitDate)) : b.exitDate.slice(0, 7);
    (map[key] ??= []).push(b);
  }
  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, bs]) => {
      const wins = bs.filter((b) => b.realizedPl > 0).length;
      return {
        key,
        label:       formatLabel(key, granularity),
        realizedPl:  bs.reduce((s, b) => s + b.realizedPl, 0),
        winRate:     (wins / bs.length) * 100,
        avgReturn:   mean(bs.map((b) => b.returnPct)),
        avgHoldDays: mean(bs.map((b) => b.holdDays)),
        tradeCount:  bs.length,
      };
    });
}

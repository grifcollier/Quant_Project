import type { AlpacaActivity } from './alpaca';

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

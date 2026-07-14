import { NextResponse } from 'next/server';
import { getActivities, type AlpacaActivity } from '@/lib/alpaca';

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

interface Lot {
  price: number;
  qty: number;
  date: string;
}

function matchTrades(fills: AlpacaActivity[]): TradeRecord[] {
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
        let remaining = qty;
        while (remaining > 0 && shortLots[symbol].length > 0) {
          const lot = shortLots[symbol][0];
          const matched = Math.min(remaining, lot.qty);
          trades.push({
            symbol, side: 'short',
            entryDate: lot.date, exitDate: date,
            entryPrice: lot.price, exitPrice: price, qty: matched,
            realizedPl: (lot.price - price) * matched,
            returnPct: (lot.price / price - 1) * 100,
            holdDays: Math.round((new Date(date).getTime() - new Date(lot.date).getTime()) / 86_400_000),
          });
          lot.qty -= matched;
          remaining -= matched;
          if (lot.qty <= 0) shortLots[symbol].shift();
        }
      } else {
        longLots[symbol].push({ price, qty, date });
      }
    } else if (side === 'sell' || side === 'sell_short') {
      // `sell_short` opens a short; `sell` reduces a long. Both close longs
      // FIFO first, remainder opens a short. (Mirror of lib/trades.ts.)
      if (longLots[symbol].length > 0) {
        let remaining = qty;
        while (remaining > 0 && longLots[symbol].length > 0) {
          const lot = longLots[symbol][0];
          const matched = Math.min(remaining, lot.qty);
          trades.push({
            symbol, side: 'long',
            entryDate: lot.date, exitDate: date,
            entryPrice: lot.price, exitPrice: price, qty: matched,
            realizedPl: (price - lot.price) * matched,
            returnPct: (price / lot.price - 1) * 100,
            holdDays: Math.round((new Date(date).getTime() - new Date(lot.date).getTime()) / 86_400_000),
          });
          lot.qty -= matched;
          remaining -= matched;
          if (lot.qty <= 0) longLots[symbol].shift();
        }
      } else {
        shortLots[symbol].push({ price, qty, date });
      }
    }
  }

  return trades.sort((a, b) => new Date(b.exitDate).getTime() - new Date(a.exitDate).getTime());
}

export async function GET() {
  try {
    const activities = await getActivities();
    const trades = matchTrades([...activities].reverse());

    const totalPl   = trades.reduce((s, t) => s + t.realizedPl, 0);
    const winCount  = trades.filter(t => t.realizedPl > 0).length;
    const winRate   = trades.length > 0 ? (winCount / trades.length) * 100 : 0;
    const avgReturn = trades.length > 0 ? trades.reduce((s, t) => s + t.returnPct, 0) / trades.length : 0;

    return NextResponse.json({ trades, totalPl, winRate, avgReturn, tradeCount: trades.length });
  } catch (e: unknown) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}

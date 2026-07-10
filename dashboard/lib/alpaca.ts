const BASE = 'https://paper-api.alpaca.markets';

function headers() {
  return {
    'APCA-API-KEY-ID': process.env.ALPACA_KEY ?? '',
    'APCA-API-SECRET-KEY': process.env.ALPACA_SECRET ?? '',
    'Content-Type': 'application/json',
  };
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: headers(), cache: 'no-store' });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Alpaca ${path}: ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface AlpacaAccount {
  equity: string;
  buying_power: string;
  cash: string;
  last_equity: string;
  portfolio_value: string;
  daytrade_count: number;
  pattern_day_trader: boolean;
}

export interface AlpacaPosition {
  symbol: string;
  qty: string;
  side: string;
  market_value: string;
  cost_basis: string;
  unrealized_pl: string;
  unrealized_plpc: string;
  avg_entry_price: string;
  current_price: string;
}

export interface AlpacaOrder {
  id: string;
  symbol: string;
  side: string;
  filled_qty: string;
  filled_avg_price: string | null;
  filled_at: string | null;
  status: string;
  type: string;
  notional: string | null;
  created_at: string;
}

export interface AlpacaActivity {
  id: string;
  activity_type: string;
  symbol: string;
  side: string;
  qty: string;
  price: string;
  transaction_time: string;
  cum_qty: string;
  leaves_qty: string;
}

export interface AlpacaPortfolioHistory {
  timestamp: number[];        // epoch seconds, one per period
  equity: (number | null)[];  // account equity at each timestamp
  profit_loss: (number | null)[];
  profit_loss_pct: (number | null)[];
  base_value: number;
  timeframe: string;
}

export const getAccount   = () => get<AlpacaAccount>('/v2/account');
export const getPositions = () => get<AlpacaPosition[]>('/v2/positions');
export const getOrders    = () => get<AlpacaOrder[]>('/v2/orders?status=all&limit=500&direction=desc');

// Daily account equity series for Sharpe/Sortino/drawdown. `period` is Alpaca's
// number+unit form (D/W/M/A); 'all' spans the account's full history.
export const getPortfolioHistory = (period = 'all', timeframe = '1D') =>
  get<AlpacaPortfolioHistory>(
    `/v2/account/portfolio/history?period=${period}&timeframe=${timeframe}&extended_hours=false`,
  );
export async function getActivities(): Promise<AlpacaActivity[]> {
  const all: AlpacaActivity[] = [];
  let pageToken: string | null = null;
  do {
    const qs: string = pageToken
      ? `activity_types=FILL&page_size=100&direction=desc&page_token=${encodeURIComponent(pageToken)}`
      : `activity_types=FILL&page_size=100&direction=desc`;
    const page = await get<AlpacaActivity[]>(`/v2/account/activities?${qs}`);
    all.push(...page);
    pageToken = page.length === 100 ? page[page.length - 1].id : null;
  } while (pageToken !== null);
  return all;
}

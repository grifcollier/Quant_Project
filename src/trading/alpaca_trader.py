"""Alpaca paper trading client wrapper."""

import os


def _get_client():
    from alpaca.trading.client import TradingClient

    # Prefer paper-specific keys; fall back to general keys
    api_key    = os.environ.get("ALPACA_PAPER_KEY")    or os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_PAPER_SECRET") or os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        raise ValueError(
            "Paper trading keys not set.\n"
            "Set ALPACA_PAPER_KEY and ALPACA_PAPER_SECRET (from alpaca.markets > Paper Trading > API Keys).\n"
            "These are separate from your live account keys."
        )

    return TradingClient(api_key=api_key, secret_key=secret_key, paper=True)


def get_account() -> dict:
    """Return account summary: equity, buying_power, cash."""
    acct = _get_client().get_account()
    return {
        "equity":        float(acct.equity),
        "buying_power":  float(acct.buying_power),
        "cash":          float(acct.cash),
    }


def get_positions() -> dict:
    """Return current positions as {symbol: current_notional_dollars}."""
    positions = _get_client().get_all_positions()
    return {p.symbol: float(p.market_value) for p in positions}


ENTRY_DATE_LOOKBACK_DAYS = 180
_FLAT_QTY_TOL = 1e-6   # fractional fills never sum to exactly zero


def _entry_dates_from_fills(orders, pos_qty: dict) -> dict:
    """
    Derive each open position's entry date by replaying its fills chronologically.

    A position's entry is the most recent flat -> non-flat transition, so a symbol
    that has been closed and reopened reports the age of the *current* position
    rather than the age of its first-ever fill. This mirrors the backtester, which
    resets ``entry_date`` on every entry (src/strategies/basket/backtest.py).

    Parameters
    ----------
    orders  : Alpaca order objects, any order (sorted internally)
    pos_qty : {symbol: signed qty currently held}, used to verify the replay

    A symbol is omitted from the result when the replayed quantity disagrees with
    the broker's actual quantity, which means the fill history is truncated and
    the position opened before the lookback window. Omitted means "unknown", and
    callers must not treat it as "old".
    """
    from alpaca.trading.enums import OrderSide

    fills = [
        o for o in orders
        if o.symbol in pos_qty and o.filled_at is not None and o.filled_qty
    ]
    fills.sort(key=lambda o: o.filled_at)

    running    = {}   # symbol -> signed qty held so far
    open_dates = {}   # symbol -> filled_at of the fill that opened the current position
    for o in fills:
        qty = float(o.filled_qty)
        if qty == 0:
            continue
        sign = -1.0 if o.side == OrderSide.SELL else 1.0
        prev = running.get(o.symbol, 0.0)
        curr = prev + sign * qty
        running[o.symbol] = curr

        if abs(prev) <= _FLAT_QTY_TOL and abs(curr) > _FLAT_QTY_TOL:
            open_dates[o.symbol] = o.filled_at
        elif abs(curr) <= _FLAT_QTY_TOL:
            open_dates.pop(o.symbol, None)

    # Drop any symbol whose replay doesn't land on the quantity actually held —
    # the visible history is partial, so its "entry" would be an artefact.
    for sym, actual in pos_qty.items():
        replayed = running.get(sym, 0.0)
        if abs(replayed - actual) > max(_FLAT_QTY_TOL, 1e-4 * abs(actual)):
            open_dates.pop(sym, None)

    return open_dates


def get_position_details() -> dict:
    """
    Return positions as {symbol: {"notional": float, "created_at": datetime}}.

    ``created_at`` is the entry date of the currently-open position. Alpaca's
    Position object has no such field, so it is reconstructed from fill history.
    It is None when the fill history is too short to locate the entry, which
    callers must treat as "unknown" rather than "old".
    """
    from alpaca.trading.requests import GetOrdersRequest
    from datetime import datetime, timezone, timedelta

    client    = _get_client()
    positions = client.get_all_positions()
    pos_qty   = {p.symbol: float(p.qty) for p in positions}   # negative when short

    open_dates = {}
    if pos_qty:
        after  = datetime.now(tz=timezone.utc) - timedelta(days=ENTRY_DATE_LOOKBACK_DAYS)
        orders = client.get_orders(
            filter=GetOrdersRequest(status="closed", after=after, limit=500)
        )
        open_dates = _entry_dates_from_fills(orders, pos_qty)

    return {
        p.symbol: {
            "notional":   float(p.market_value),
            "created_at": open_dates.get(p.symbol),
        }
        for p in positions
    }


def place_notional_order(symbol: str, notional: float, side) -> object:
    """
    Place a market order for a dollar notional amount.

    Parameters
    ----------
    symbol   : ticker symbol (e.g. "SPY")
    notional : dollar amount to buy/sell (must be positive)
    side     : OrderSide.BUY or OrderSide.SELL
    """
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import TimeInForce

    request = MarketOrderRequest(
        symbol=symbol,
        notional=round(abs(notional), 2),
        side=side,
        time_in_force=TimeInForce.DAY,
    )
    return _get_client().submit_order(request)


def place_qty_order(symbol: str, qty: int, side) -> object:
    """
    Place a market order for a whole-share quantity.

    Required for short sells — Alpaca does not allow fractional short sales.
    """
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import TimeInForce

    request = MarketOrderRequest(
        symbol=symbol,
        qty=int(qty),
        side=side,
        time_in_force=TimeInForce.DAY,
    )
    return _get_client().submit_order(request)


def close_position(symbol: str) -> object:
    """Close the entire open position for a single symbol."""
    return _get_client().close_position(symbol)


def cancel_all_orders():
    """Cancel all open orders."""
    _get_client().cancel_orders()


def close_all_positions():
    """Close all open positions at market."""
    _get_client().close_all_positions(cancel_orders=True)

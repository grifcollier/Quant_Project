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

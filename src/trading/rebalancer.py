"""Convert vol-targeted weights to rebalancing orders."""

import pandas as pd


def weights_to_orders(
    target_weights: pd.Series,
    current_prices: pd.Series,
    capital: float,
    current_positions: dict,
    min_order_dollars: float = 50.0,
) -> list:
    """
    Compute the orders needed to move from current positions to target weights.

    Parameters
    ----------
    target_weights    : weights_df.iloc[-1] — today's target weight per ticker.
    current_prices    : prices_df.iloc[-1] — latest close per ticker.
    capital           : total portfolio capital in dollars.
    current_positions : {symbol: current_notional_dollars} from get_positions().
    min_order_dollars : skip orders smaller than this (avoids tiny rebalances).

    Returns
    -------
    List of dicts: [{symbol, side, order_notional, target_notional, current_notional}]
    """
    from alpaca.trading.enums import OrderSide

    orders = []
    all_symbols = set(target_weights.index) | set(current_positions.keys())

    for symbol in sorted(all_symbols):
        target_w   = float(target_weights.get(symbol, 0.0))
        target_not = target_w * capital
        current_not = float(current_positions.get(symbol, 0.0))
        order_not   = target_not - current_not

        if abs(order_not) < min_order_dollars:
            continue

        side = OrderSide.BUY if order_not > 0 else OrderSide.SELL
        orders.append({
            "symbol":          symbol,
            "side":            side,
            "order_notional":  order_not,
            "target_notional": target_not,
            "current_notional": current_not,
            "target_pct":      target_w,
            "current_pct":     current_not / capital if capital else 0.0,
        })

    return orders

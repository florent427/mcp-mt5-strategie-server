"""
Trading — orders, positions, history.
Based on Qoyyuum/mcp-metatrader5-server.
"""
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5


# Order type mapping
ORDER_TYPES = {
    "BUY": mt5.ORDER_TYPE_BUY,
    "SELL": mt5.ORDER_TYPE_SELL,
    "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
    "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
    "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
    "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
}


def send_order(
    symbol: str,
    order_type: str,
    volume: float,
    price: Optional[float] = None,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    comment: str = "",
    magic: int = 0,
    deviation: int = 20,
) -> dict:
    """Send a trading order.

    Args:
        symbol: e.g. "BTCUSD"
        order_type: BUY, SELL, BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP
        volume: lot size
        price: required for pending orders (limit/stop)
        sl: stop loss price (optional)
        tp: take profit price (optional)
        comment: free text
        magic: magic number (EA identifier)
        deviation: max slippage in points (for market orders)
    """
    ot = ORDER_TYPES.get(order_type.upper())
    if ot is None:
        return {"success": False, "error": f"Invalid order type: {order_type}"}

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"success": False, "error": f"Symbol {symbol} not available"}

    if price is None:
        price = tick.ask if ot in (mt5.ORDER_TYPE_BUY,) else tick.bid

    is_market = ot in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL)
    request = {
        "action": mt5.TRADE_ACTION_DEAL if is_market else mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": ot,
        "price": price,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    if sl is not None:
        request["sl"] = sl
    if tp is not None:
        request["tp"] = tp

    result = mt5.order_send(request)
    if result is None:
        return {"success": False, "error": str(mt5.last_error())}
    return {
        "success": result.retcode == mt5.TRADE_RETCODE_DONE,
        "retcode": result.retcode,
        "deal": result.deal,
        "order": result.order,
        "volume": result.volume,
        "price": result.price,
        "comment": result.comment,
    }


def check_order(
    symbol: str,
    order_type: str,
    volume: float,
    price: Optional[float] = None,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
) -> dict:
    """Dry-run order check (calc margins, costs)."""
    ot = ORDER_TYPES.get(order_type.upper())
    if ot is None:
        return {"error": f"Invalid order type: {order_type}"}
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"error": f"Symbol {symbol} not available"}
    if price is None:
        price = tick.ask if ot == mt5.ORDER_TYPE_BUY else tick.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": ot,
        "price": price,
    }
    if sl is not None: request["sl"] = sl
    if tp is not None: request["tp"] = tp
    result = mt5.order_check(request)
    if result is None:
        return {"error": str(mt5.last_error())}
    return result._asdict()


def get_positions() -> list[dict]:
    """Get all open positions."""
    pos = mt5.positions_get()
    if pos is None:
        return []
    return [p._asdict() for p in pos]


def get_pending_orders() -> list[dict]:
    """Get all pending orders."""
    orders = mt5.orders_get()
    if orders is None:
        return []
    return [o._asdict() for o in orders]


def get_history_deals(from_date: str, to_date: str) -> list[dict]:
    """Get historical deals between two dates (ISO format)."""
    deals = mt5.history_deals_get(
        datetime.fromisoformat(from_date),
        datetime.fromisoformat(to_date),
    )
    if deals is None:
        return []
    return [d._asdict() for d in deals]


def close_position(ticket: int, deviation: int = 20) -> dict:
    """Close a position by ticket."""
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return {"success": False, "error": f"Position {ticket} not found"}
    p = pos[0]
    tick = mt5.symbol_info_tick(p.symbol)
    if tick is None:
        return {"success": False, "error": str(mt5.last_error())}
    order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": p.symbol,
        "volume": p.volume,
        "type": order_type,
        "position": ticket,
        "price": price,
        "deviation": deviation,
        "magic": p.magic,
        "comment": "Closed via MCP",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result is None:
        return {"success": False, "error": str(mt5.last_error())}
    return {
        "success": result.retcode == mt5.TRADE_RETCODE_DONE,
        "retcode": result.retcode,
    }

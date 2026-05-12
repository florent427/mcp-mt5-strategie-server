"""
Market data — symbols, bars, ticks.
Based on Qoyyuum/mcp-metatrader5-server, with type-safety improvements.
"""
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd


# Timeframe mapping
TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}


def get_symbols(group: Optional[str] = None) -> list[dict]:
    """List all available symbols (optionally filtered by group, e.g. 'Forex')."""
    syms = mt5.symbols_get(group) if group else mt5.symbols_get()
    if syms is None:
        return []
    return [s._asdict() for s in syms]


def get_symbol_info(symbol: str) -> dict:
    """Get detailed info for a single symbol."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return {"error": f"Symbol {symbol} not found: {mt5.last_error()}"}
    return info._asdict()


def get_symbol_tick(symbol: str) -> dict:
    """Get last tick for a symbol."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"error": str(mt5.last_error())}
    return tick._asdict()


def get_bars(
    symbol: str,
    timeframe: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    count: int = 1000,
) -> list[dict]:
    """Get historical bars for a symbol.

    Args:
        symbol: e.g. "BTCUSD"
        timeframe: One of M1, M5, M15, M30, H1, H4, D1, W1, MN1
        from_date: ISO format date (e.g. "2024-01-01"). If None, fetches `count` recent bars.
        to_date: ISO format date for range mode. If None, count is used from from_date.
        count: Number of bars to fetch (when no to_date)
    """
    tf = TIMEFRAMES.get(timeframe.upper())
    if tf is None:
        return [{"error": f"Invalid timeframe: {timeframe}"}]

    if from_date and to_date:
        bars = mt5.copy_rates_range(
            symbol, tf,
            datetime.fromisoformat(from_date),
            datetime.fromisoformat(to_date),
        )
    elif from_date:
        bars = mt5.copy_rates_from(
            symbol, tf,
            datetime.fromisoformat(from_date),
            count,
        )
    else:
        bars = mt5.copy_rates_from_pos(symbol, tf, 0, count)

    if bars is None:
        return [{"error": str(mt5.last_error())}]

    df = pd.DataFrame(bars)
    df["time"] = pd.to_datetime(df["time"], unit="s").astype(str)
    return df.to_dict("records")


def get_ticks(
    symbol: str,
    from_date: str,
    to_date: Optional[str] = None,
    count: int = 10000,
) -> list[dict]:
    """Get tick data for a symbol.

    KEY FEATURE: This is the actual tick-by-tick history from MT5.
    Use to feed your custom tick-based backtester for precision validation.

    Args:
        symbol: e.g. "BTCUSD"
        from_date: ISO format date
        to_date: ISO format date (if None, fetches `count` ticks from from_date)
        count: Number of ticks to fetch (when no to_date)
    """
    if to_date:
        ticks = mt5.copy_ticks_range(
            symbol,
            datetime.fromisoformat(from_date),
            datetime.fromisoformat(to_date),
            mt5.COPY_TICKS_ALL,
        )
    else:
        ticks = mt5.copy_ticks_from(
            symbol,
            datetime.fromisoformat(from_date),
            count,
            mt5.COPY_TICKS_ALL,
        )

    if ticks is None:
        return [{"error": str(mt5.last_error())}]

    df = pd.DataFrame(ticks)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], unit="s").astype(str)
    return df.to_dict("records")

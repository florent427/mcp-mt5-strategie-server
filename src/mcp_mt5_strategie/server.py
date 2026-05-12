"""
FastMCP server exposing all MT5 capabilities :
  - Data : symbols, bars, ticks (port from Qoyyuum)
  - Trading : orders, positions (port from Qoyyuum)
  - MQL5 dev : write, read, compile (NEW)
  - Backtest : run, parse reports (NEW)
  - Optimization : parameter sweep, walk-forward (NEW)
"""
from typing import Any, Optional

from fastmcp import FastMCP

from .tools import connection, market_data, trading, mql5_dev, backtest, optimization
from .tools.backtest import BacktestConfig
from .tools.optimization import OptimizationConfig


mcp = FastMCP("mt5-strategie")


# ============================================================
# Connection
# ============================================================

@mcp.tool()
def initialize(path: Optional[str] = None) -> dict:
    """Initialize the MT5 terminal connection.

    Args:
        path: Optional path to terminal64.exe. Defaults to standard install location.
    """
    return connection.initialize_mt5(path)


@mcp.tool()
def login(account: int, password: str, server: str) -> dict:
    """Login to a trading account.

    Args:
        account: Account number
        password: Account password
        server: Broker server name
    """
    return connection.login_account(account, password, server)


@mcp.tool()
def shutdown() -> dict:
    """Close the MT5 terminal connection."""
    return connection.shutdown_mt5()


@mcp.tool()
def get_account_info() -> dict:
    """Get current account information (balance, equity, margin, etc.)."""
    return connection.get_account_info()


@mcp.tool()
def get_terminal_info() -> dict:
    """Get MT5 terminal information (build, paths, connection state)."""
    return connection.get_terminal_info()


# ============================================================
# Market Data
# ============================================================

@mcp.tool()
def get_symbols(group: Optional[str] = None) -> list[dict]:
    """List available symbols, optionally filtered by group (e.g. 'Forex')."""
    return market_data.get_symbols(group)


@mcp.tool()
def get_symbol_info(symbol: str) -> dict:
    """Get detailed info for a single symbol."""
    return market_data.get_symbol_info(symbol)


@mcp.tool()
def get_symbol_tick(symbol: str) -> dict:
    """Get last tick for a symbol."""
    return market_data.get_symbol_tick(symbol)


@mcp.tool()
def get_bars(
    symbol: str,
    timeframe: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    count: int = 1000,
) -> list[dict]:
    """Get historical OHLC bars for a symbol.

    Args:
        symbol: e.g. "BTCUSD"
        timeframe: M1, M5, M15, M30, H1, H4, D1, W1, MN1
        from_date: ISO date "2024-01-01". If None, fetches `count` recent bars.
        to_date: ISO date for range mode.
        count: Number of bars when no to_date.
    """
    return market_data.get_bars(symbol, timeframe, from_date, to_date, count)


@mcp.tool()
def get_ticks(
    symbol: str,
    from_date: str,
    to_date: Optional[str] = None,
    count: int = 10000,
) -> list[dict]:
    """Get tick data for a symbol — REAL HISTORICAL TICKS from MT5.

    Use to feed a custom tick-based backtester for precision validation.

    Args:
        symbol: e.g. "BTCUSD"
        from_date: ISO date
        to_date: ISO date (if None, fetches `count` ticks from from_date)
        count: Number of ticks when no to_date.
    """
    return market_data.get_ticks(symbol, from_date, to_date, count)


# ============================================================
# Trading
# ============================================================

@mcp.tool()
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
        price: required for pending orders
        sl: stop loss price
        tp: take profit price
        comment: free text
        magic: magic number
        deviation: max slippage (market orders)
    """
    return trading.send_order(symbol, order_type, volume, price, sl, tp, comment, magic, deviation)


@mcp.tool()
def check_order(
    symbol: str,
    order_type: str,
    volume: float,
    price: Optional[float] = None,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
) -> dict:
    """Dry-run order check (validate, calc margins)."""
    return trading.check_order(symbol, order_type, volume, price, sl, tp)


@mcp.tool()
def get_positions() -> list[dict]:
    """Get all open positions."""
    return trading.get_positions()


@mcp.tool()
def get_pending_orders() -> list[dict]:
    """Get all pending orders."""
    return trading.get_pending_orders()


@mcp.tool()
def get_history_deals(from_date: str, to_date: str) -> list[dict]:
    """Get historical deals between two dates (ISO format)."""
    return trading.get_history_deals(from_date, to_date)


@mcp.tool()
def close_position(ticket: int, deviation: int = 20) -> dict:
    """Close a position by ticket."""
    return trading.close_position(ticket, deviation)


# ============================================================
# MQL5 Development — NEW
# ============================================================

@mcp.tool()
def write_mql5(
    filename: str,
    code: str,
    file_type: str = "expert",
) -> dict:
    """Write a MQL5 source file (.mq5) to MT5's directory.

    Args:
        filename: e.g. "MyEA.mq5" or "MyEA"
        code: Full MQL5 source code
        file_type: "expert", "script", "indicator", "library"
    """
    return mql5_dev.write_mql5_file(filename, code, file_type)


@mcp.tool()
def read_mql5(filename: str, file_type: str = "expert") -> dict:
    """Read a MQL5 source file."""
    return mql5_dev.read_mql5_file(filename, file_type)


@mcp.tool()
def list_mql5_files(file_type: str = "expert") -> list[dict]:
    """List all .mq5 and .ex5 files in the target directory."""
    return mql5_dev.list_mql5_files(file_type)


@mcp.tool()
def compile_mql5(filename: str, file_type: str = "expert") -> dict:
    """Compile a MQL5 source file via MetaEditor CLI.

    Returns success status, errors, warnings, and path to .ex5 if compiled.
    """
    return mql5_dev.compile_mql5(filename, file_type)


# ============================================================
# Backtest — NEW
# ============================================================

@mcp.tool()
def run_backtest(
    symbol: str,
    timeframe: str,
    expert_name: str,
    from_date: str,
    to_date: str,
    model: str = "every_tick_real",
    deposit: float = 100_000.0,
    leverage: int = 100,
    currency: str = "USD",
    inputs: Optional[dict] = None,
    visual: bool = False,
    timeout_sec: Optional[int] = None,
) -> dict:
    """Run a backtest in MT5 Strategy Tester (native, tick-by-tick capable).

    Args:
        symbol: e.g. "BTCUSD"
        timeframe: M1, M5, M15, M30, H1, H4, D1
        expert_name: Name of compiled EA (without .ex5)
        from_date: ISO date "2024-01-01"
        to_date: ISO date "2025-12-31"
        model: "every_tick_real" (most precise), "every_tick", "1m_ohlc", "open_prices"
        deposit: Initial capital
        leverage: Leverage ratio (e.g. 100 for 1:100)
        currency: Account currency
        inputs: EA input parameters as {name: value}
        visual: Run with GUI visible (default False = headless)
        timeout_sec: Max runtime (default from config)

    Returns:
        {success, stats, trades, equity_curve, report_path}
    """
    cfg = BacktestConfig(
        symbol=symbol,
        timeframe=timeframe,
        expert_name=expert_name,
        from_date=from_date,
        to_date=to_date,
        model=model,
        deposit=deposit,
        leverage=leverage,
        currency=currency,
        inputs=inputs or {},
        visual=visual,
        timeout_sec=timeout_sec,
    )
    return backtest.run_backtest(cfg)


# ============================================================
# Optimization — NEW
# ============================================================

@mcp.tool()
def run_optimization(
    symbol: str,
    timeframe: str,
    expert_name: str,
    from_date: str,
    to_date: str,
    inputs: dict,
    criterion: str = "sharpe_ratio_max",
    algorithm: str = "genetic",
    model: str = "1m_ohlc",
    deposit: float = 100_000.0,
    leverage: int = 100,
    forward_mode: str = "none",
    forward_date: Optional[str] = None,
    timeout_sec: Optional[int] = None,
) -> dict:
    """Run parameter optimization in MT5 Strategy Tester.

    Inputs format for each param :
        - Fixed value: "MyParam": 20
        - Range: "MyParam": {"start": 10, "step": 1, "stop": 50}

    Args:
        symbol: e.g. "BTCUSD"
        timeframe: M1, M5, M15, M30, H1, H4, D1
        expert_name: Compiled EA name
        from_date / to_date: ISO dates
        inputs: dict of params (fixed value or range dict)
        criterion: balance_max, profit_factor_max, expected_payoff_max,
                  drawdown_min, recovery_factor_max, sharpe_ratio_max, custom
        algorithm: "genetic" (faster) or "complete" (brute force)
        model: same as backtest
        forward_mode: none, half, third, quarter, custom (for walk-forward)
        forward_date: required if forward_mode=custom

    Returns:
        {success, passes, best_params, best_stats, all_passes}
    """
    cfg = OptimizationConfig(
        symbol=symbol,
        timeframe=timeframe,
        expert_name=expert_name,
        from_date=from_date,
        to_date=to_date,
        inputs=inputs,
        criterion=criterion,
        algorithm=algorithm,
        model=model,
        deposit=deposit,
        leverage=leverage,
        forward_mode=forward_mode,
        forward_date=forward_date,
        timeout_sec=timeout_sec,
    )
    return optimization.run_optimization(cfg)


# ============================================================
# Main
# ============================================================

def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

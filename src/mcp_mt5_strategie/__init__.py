"""
MCP MetaTrader 5 Strategie Server

A comprehensive MCP server exposing the full MetaTrader 5 capability set:
- Data access (historic bars, ticks)
- Live trading (orders, positions)
- MQL5 development (write, compile, link)
- Strategy Tester (backtest, optimization)
- Report parsing (XML, HTML)

Built on top of Qoyyuum/mcp-metatrader5-server (data/trading layer),
extended with native MT5 CLI integration for the dev/test workflow.
"""

__version__ = "0.1.0"

from .server import main

__all__ = ["main"]

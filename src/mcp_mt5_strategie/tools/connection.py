"""
Connection management — initialize / login / shutdown.
Based on Qoyyuum/mcp-metatrader5-server.
"""
from typing import Optional

import MetaTrader5 as mt5


def initialize_mt5(path: Optional[str] = None) -> dict:
    """Initialize the MT5 terminal connection.

    Args:
        path: Optional path to terminal64.exe. If None, uses default.

    Returns:
        {success: bool, error: str | None, version: tuple | None}
    """
    if path:
        ok = mt5.initialize(path=path)
    else:
        ok = mt5.initialize()

    if not ok:
        return {
            "success": False,
            "error": str(mt5.last_error()),
            "version": None,
        }

    return {
        "success": True,
        "error": None,
        "version": mt5.version(),
    }


def login_account(account: int, password: str, server: str) -> dict:
    """Login to a trading account.

    Args:
        account: Account number (int)
        password: Account password
        server: Broker server name

    Returns:
        {success: bool, account_info: dict | None, error: str | None}
    """
    ok = mt5.login(login=account, password=password, server=server)
    if not ok:
        return {
            "success": False,
            "account_info": None,
            "error": str(mt5.last_error()),
        }
    info = mt5.account_info()
    return {
        "success": True,
        "account_info": info._asdict() if info else None,
        "error": None,
    }


def shutdown_mt5() -> dict:
    """Close the MT5 terminal connection."""
    mt5.shutdown()
    return {"success": True}


def get_account_info() -> dict:
    """Get current account information."""
    info = mt5.account_info()
    if info is None:
        return {"error": str(mt5.last_error())}
    return info._asdict()


def get_terminal_info() -> dict:
    """Get terminal information (path, build, connection status)."""
    info = mt5.terminal_info()
    if info is None:
        return {"error": str(mt5.last_error())}
    return info._asdict()

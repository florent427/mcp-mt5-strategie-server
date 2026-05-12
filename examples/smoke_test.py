"""
Smoke test — verifies the MCP server can be imported, configured, and that
the underlying MT5 toolchain is reachable.

Does NOT run a full backtest (that needs an active MT5 session + tick history).
Run this first to confirm install. Then move on to run_full_workflow.py.

Usage :
    # Optional, only if MT5 isn't at default path
    set MT5_TERMINAL_PATH=C:\\Program Files\\FTMO Global Markets MT5 Terminal\\terminal64.exe
    set MT5_METAEDITOR_PATH=C:\\Program Files\\FTMO Global Markets MT5 Terminal\\MetaEditor64.exe

    python examples/smoke_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path


def step(n: int, total: int, msg: str) -> None:
    print(f"[{n}/{total}] {msg}")


def main() -> int:
    TOTAL = 5

    # 1. Package import
    step(1, TOTAL, "Importing mcp_mt5_strategie...")
    try:
        from mcp_mt5_strategie import __version__
        from mcp_mt5_strategie.config import config
        from mcp_mt5_strategie.tools import connection, mql5_dev
    except Exception as e:
        print(f"    FAIL — import error: {e}")
        return 1
    print(f"    OK — version {__version__}")

    # 2. Config paths
    step(2, TOTAL, "Resolving MT5 paths from config...")
    print(f"    terminal_path  : {config.terminal_path}")
    print(f"    metaeditor_path: {config.metaeditor_path}")
    print(f"    data_path      : {config.data_path}")
    if not config.terminal_path.exists():
        print(f"    WARN — terminal64.exe not found at {config.terminal_path}")
        print("    Set MT5_TERMINAL_PATH env var to your install location.")
    if not config.metaeditor_path.exists():
        print(f"    WARN — metaeditor64.exe not found at {config.metaeditor_path}")
    try:
        mql5 = config.resolve_mql5_dir()
        print(f"    MQL5 dir       : {mql5}")
        print(f"    Experts        : {config.experts_dir()}")
    except FileNotFoundError as e:
        print(f"    WARN — MQL5 dir lookup failed: {e}")

    # 3. MT5 connection (read-only — doesn't trade)
    step(3, TOTAL, "Initializing MT5 terminal connection...")
    try:
        init = connection.initialize_mt5()
        if init.get("success"):
            print(f"    OK — connected to terminal")
            ti = connection.get_terminal_info()
            print(f"    Build={ti.get('build')} Company={ti.get('company')}")
        else:
            print(f"    WARN — initialize returned: {init}")
    except Exception as e:
        print(f"    WARN — {type(e).__name__}: {e}")

    # 4. MQL5 read (just list existing experts)
    step(4, TOTAL, "Listing existing experts in MT5 Experts/...")
    try:
        files = mql5_dev.list_mql5_files(file_type="expert")
        print(f"    OK — {len(files)} files found")
        for f in files[:5]:
            print(f"      - {f.get('name')}")
        if len(files) > 5:
            print(f"      ... and {len(files) - 5} more")
    except Exception as e:
        print(f"    WARN — {type(e).__name__}: {e}")

    # 5. Cleanup
    step(5, TOTAL, "Shutting down MT5 connection...")
    try:
        connection.shutdown_mt5()
        print("    OK")
    except Exception as e:
        print(f"    WARN — {e}")

    print("\nSmoke test done. If all 5 steps say OK, the MCP server is ready.")
    print("For a real backtest, run examples/run_full_workflow.py (needs an")
    print("active MT5 login + tick history for the symbol/range you choose).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

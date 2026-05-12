"""
Full workflow example — drives the MCP server's underlying functions directly
(no MCP transport, just Python calls) to demonstrate the end-to-end flow.

Steps:
  1. Initialize MT5
  2. Write the Fib 0.900 EA source
  3. Compile it
  4. Run a tick-by-tick backtest
  5. Optimize the Lookback parameter
  6. Print best params + stats

Run :
    python examples/run_full_workflow.py
"""
from __future__ import annotations

from pathlib import Path

from mcp_mt5_strategie.tools import connection, mql5_dev, backtest, optimization
from mcp_mt5_strategie.tools.backtest import BacktestConfig
from mcp_mt5_strategie.tools.optimization import OptimizationConfig


HERE = Path(__file__).parent
EA_SOURCE = HERE / "fib_090_ea.mq5"
EA_NAME = "fib_090_ea"  # without extension


def main() -> None:
    # ---------- 1. Connect ----------
    print("[1/5] Initializing MT5 terminal...")
    init = connection.initialize_mt5()
    if not init.get("success"):
        raise SystemExit(f"MT5 init failed: {init}")
    print(f"    OK — build {init.get('build')}, broker={init.get('company')}")

    # ---------- 2. Write EA ----------
    print(f"[2/5] Writing {EA_NAME}.mq5 to MT5 Experts folder...")
    code = EA_SOURCE.read_text(encoding="utf-8")
    wr = mql5_dev.write_mql5_file(f"{EA_NAME}.mq5", code, file_type="expert")
    print(f"    Wrote {wr['path']}")

    # ---------- 3. Compile ----------
    print("[3/5] Compiling EA via MetaEditor CLI...")
    comp = mql5_dev.compile_mql5(EA_NAME, file_type="expert")
    if not comp["success"]:
        print("    COMPILE FAILED")
        for err in comp.get("errors", []):
            print(f"      ERROR: {err}")
        raise SystemExit(1)
    if comp.get("warnings"):
        print(f"    {len(comp['warnings'])} warning(s)")
    print(f"    OK -> {comp.get('ex5_path')}")

    # ---------- 4. Backtest ----------
    print("[4/5] Running tick-by-tick backtest (Jan-Jun 2025, BTCUSD M5)...")
    bt_cfg = BacktestConfig(
        symbol="BTCUSD",
        timeframe="M5",
        expert_name=EA_NAME,
        from_date="2025-01-01",
        to_date="2025-06-01",
        model="every_tick_real",
        deposit=100_000.0,
        leverage=100,
        inputs={
            "Lookback": 20,
            "FibLevel": 0.9,
            "FibExit": 0.5,
            "LotSize": 0.10,
            "LongOnly": True,
        },
    )
    bt = backtest.run_backtest(bt_cfg)
    if not bt["success"]:
        raise SystemExit(f"Backtest failed: {bt.get('error')}")
    stats = bt["stats"] or {}
    print(f"    Net profit  : {stats.get('net_profit')}")
    print(f"    Profit factor: {stats.get('profit_factor')}")
    print(f"    Max drawdown: {stats.get('max_drawdown')}")
    print(f"    Trades      : {stats.get('trades')}")
    print(f"    Sharpe      : {stats.get('sharpe_ratio')}")
    print(f"    Report      : {bt['report_path']}")
    print(f"    Elapsed     : {bt['elapsed_sec']:.1f}s")

    # ---------- 5. Optimize Lookback ----------
    print("[5/5] Optimizing Lookback (genetic, sharpe_ratio_max)...")
    opt_cfg = OptimizationConfig(
        symbol="BTCUSD",
        timeframe="M5",
        expert_name=EA_NAME,
        from_date="2025-01-01",
        to_date="2025-06-01",
        model="1m_ohlc",  # faster for opt
        inputs={
            "Lookback": {"start": 5, "step": 5, "stop": 100},
            "FibLevel": 0.9,
            "FibExit": 0.5,
            "LotSize": 0.10,
            "LongOnly": True,
        },
        criterion="sharpe_ratio_max",
        algorithm="genetic",
        forward_mode="half",  # 50/50 walk-forward split
    )
    opt = optimization.run_optimization(opt_cfg)
    if not opt["success"]:
        raise SystemExit(f"Optimization failed: {opt.get('error')}")
    print(f"    Passes  : {opt['passes']}")
    print(f"    Best    : {opt['best_params']}")
    print(f"    Stats   : {opt['best_stats']}")
    print(f"    Elapsed : {opt['elapsed_sec']:.1f}s")

    # ---------- Cleanup ----------
    connection.shutdown_mt5()
    print("\nDone.")


if __name__ == "__main__":
    main()

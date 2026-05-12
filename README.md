# mcp-mt5-strategie-server

**MCP server for MetaTrader 5 — full native coverage: data, trading, MQL5 dev, backtest, optimization.**

Extends [Qoyyuum/mcp-metatrader5-server](https://github.com/Qoyyuum/mcp-metatrader5-server) with:

- **MQL5 development** — write, read, list, **compile** `.mq5` source files (Experts / Scripts / Indicators)
- **Native backtest** — drive MT5 Strategy Tester headlessly with `every_tick_real` precision (true tick-by-tick)
- **Parameter optimization** — genetic or brute-force, with walk-forward forward-test split
- **Report parsing** — XML/HTML reports → typed Python dicts (stats, trades, equity curve)

## Why

TradingView Pine strategies are bar-by-bar (Bar Magnifier only mitigates intra-bar fills). For honest validation
of mean-reversion / scalping strategies sensitive to tick path, you need real ticks. MT5 is the only retail
platform exposing tick-by-tick simulation with a CLI surface — this MCP wraps that surface for agents.

## Architecture

```
src/mcp_mt5_strategie/
├── server.py              # FastMCP entrypoint, @mcp.tool() decorators
├── config.py              # paths (terminal, metaeditor, data) via env vars
├── tools/
│   ├── connection.py      # initialize / login / shutdown / account_info
│   ├── market_data.py     # symbols / bars / ticks (REAL historical ticks)
│   ├── trading.py         # send_order / positions / history_deals
│   ├── mql5_dev.py        # write / read / list / compile .mq5
│   ├── backtest.py        # run_backtest → terminal64 /config:tester.ini
│   └── optimization.py    # run_optimization with criterion + algorithm
└── parsers/
    ├── report_xml.py      # parse backtest XML (lxml) with HTML fallback
    └── opt_xml.py         # parse optimization passes
```

## Install

Requires Windows + MetaTrader 5 installed.

```bash
git clone https://github.com/florent427/mcp-mt5-strategie-server.git
cd mcp-mt5-strategie-server
pip install -e .
```

### Environment

Optional env vars (defaults shown):

```
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_METAEDITOR_PATH=C:\Program Files\MetaTrader 5\metaeditor64.exe
MT5_DATA_PATH=%APPDATA%\MetaQuotes\Terminal
```

## Register with Claude

Add to `.mcp.json` (project) or Claude Desktop config:

```json
{
  "mcpServers": {
    "mt5-strategie": {
      "command": "mt5-strategie-mcp"
    }
  }
}
```

## Tools

### Connection
| Tool | Purpose |
|------|---------|
| `initialize(path?)` | Start MT5 terminal |
| `login(account, password, server)` | Authenticate broker account |
| `shutdown()` | Close terminal |
| `get_account_info()` | Balance / equity / margin |
| `get_terminal_info()` | Build / paths |

### Market data
| Tool | Purpose |
|------|---------|
| `get_symbols(group?)` | List instruments |
| `get_symbol_info(symbol)` | Spec / margin / point |
| `get_symbol_tick(symbol)` | Last bid/ask |
| `get_bars(symbol, tf, ...)` | OHLC history |
| `get_ticks(symbol, from, ...)` | **REAL** tick history |

### Trading
| Tool | Purpose |
|------|---------|
| `send_order(...)` | Market / pending order |
| `check_order(...)` | Dry-run validation |
| `get_positions()` / `get_pending_orders()` | Live state |
| `get_history_deals(from, to)` | Closed deals |
| `close_position(ticket)` | Close by ticket |

### MQL5 development *(NEW)*
| Tool | Purpose |
|------|---------|
| `write_mql5(filename, code, file_type)` | Write `.mq5` source |
| `read_mql5(filename, file_type)` | Read `.mq5` source |
| `list_mql5_files(file_type)` | List existing files |
| `compile_mql5(filename, file_type)` | Run MetaEditor CLI, return errors/warnings + `.ex5` path |

### Backtest *(NEW)*
```python
run_backtest(
  symbol="BTCUSD", timeframe="M5", expert_name="FibEA",
  from_date="2024-01-01", to_date="2025-12-31",
  model="every_tick_real",  # tick-by-tick
  deposit=100_000, leverage=100, currency="USD",
  inputs={"FibLevel": 0.9, "Lookback": 20},
)
# → {success, stats, trades, equity_curve, report_path}
```

`model` values:
- `every_tick_real` — true historical ticks (most precise)
- `every_tick` — M1 OHLC + simulated ticks
- `1m_ohlc` — M1 OHLC only
- `open_prices` — open of each bar

### Optimization *(NEW)*
```python
run_optimization(
  symbol="BTCUSD", timeframe="M5", expert_name="FibEA",
  from_date="2024-01-01", to_date="2025-12-31",
  inputs={
    "Lookback": {"start": 10, "step": 5, "stop": 50},   # optimized
    "FibLevel": 0.9,                                    # fixed
  },
  criterion="sharpe_ratio_max",
  algorithm="genetic",
  forward_mode="half",   # walk-forward 50/50
)
# → {passes, best_params, best_stats, all_passes}
```

## Workflow

```python
# 1. Write EA
write_mql5("FibEA.mq5", code=open("examples/fib_090_ea.mq5").read())

# 2. Compile
result = compile_mql5("FibEA")
assert result["success"], result["errors"]

# 3. Backtest with real ticks
bt = run_backtest(
    symbol="BTCUSD", timeframe="M5", expert_name="FibEA",
    from_date="2024-01-01", to_date="2025-06-01",
    model="every_tick_real",
    inputs={"FibLevel": 0.9, "Lookback": 20},
)
print(bt["stats"])  # net_profit, profit_factor, max_drawdown, ...

# 4. Optimize Lookback parameter
opt = run_optimization(
    symbol="BTCUSD", timeframe="M5", expert_name="FibEA",
    from_date="2024-01-01", to_date="2025-06-01",
    inputs={"FibLevel": 0.9, "Lookback": {"start": 5, "step": 5, "stop": 100}},
    criterion="sharpe_ratio_max", algorithm="genetic",
)
print(opt["best_params"], opt["best_stats"])
```

See `examples/run_full_workflow.py` for a runnable script and `examples/fib_090_ea.mq5` for a reference EA.

## Limits & caveats

- **Windows only** — MetaTrader 5 has no Linux/macOS native build.
- **Tester is exclusive** — only one terminal instance can run a backtest at a time per data folder.
- **Real ticks require download** — first `every_tick_real` run for a symbol/range will download history from the broker.
- **Optimization is slow** — genetic mode is the only practical choice for >3 parameters. Use `forward_mode` to detect overfitting.
- **Report parsing is best-effort** — MT5 has changed XML schema between builds; falls back to HTML if XML fails.

## License

MIT — see `LICENSE`.

## Credits

- Base structure inspired by [Qoyyuum/mcp-metatrader5-server](https://github.com/Qoyyuum/mcp-metatrader5-server)
- MT5 Python API by MetaQuotes
- FastMCP framework by [@jlowin](https://github.com/jlowin/fastmcp)

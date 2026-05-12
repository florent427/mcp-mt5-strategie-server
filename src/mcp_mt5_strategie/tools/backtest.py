"""
Backtest — run native MT5 Strategy Tester via terminal64.exe CLI.

The terminal can run in headless/portable mode with a config .ini file
defining symbol, dates, EA, model, inputs, etc.

THIS IS NEW — not in Qoyyuum's base server.

Reference:
  https://www.mql5.com/en/docs/runtime/running#configuration_file
"""
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from ..config import config
from ..parsers.report_xml import parse_backtest_report

BacktestModel = Literal["every_tick", "1m_ohlc", "open_prices", "every_tick_real"]

# Map our friendly names to MT5 numeric model codes
MODEL_CODES = {
    "every_tick": 0,           # OHLC of M1, simulated ticks
    "1m_ohlc": 1,              # OHLC of M1 only
    "open_prices": 2,          # Open price only
    "every_tick_real": 4,      # Real tick data (most precise, requires available ticks)
}


class BacktestConfig(BaseModel):
    """Configuration for a single backtest run."""

    symbol: str = Field(..., examples=["BTCUSD"])
    timeframe: str = Field("H1", examples=["M1", "M5", "M15", "M30", "H1", "H4", "D1"])
    expert_name: str = Field(..., description="Compiled EA name (without .ex5)")
    from_date: str = Field(..., examples=["2024-01-01"])
    to_date: str = Field(..., examples=["2025-12-31"])
    model: BacktestModel = "every_tick_real"  # default: most precise
    deposit: float = 100_000.0
    leverage: int = 100
    currency: str = "USD"
    inputs: dict[str, Any] = Field(default_factory=dict, description="EA inputs (k=v pairs)")
    visual: bool = False  # headless by default
    timeout_sec: Optional[int] = None


def run_backtest(cfg: BacktestConfig) -> dict:
    """Run a backtest in MT5 Strategy Tester.

    Returns:
        {
            success: bool,
            stats: {
                net_profit, profit_factor, max_drawdown, sharpe,
                trades, winrate, ...
            },
            trades: [{...}, ...],
            equity_curve: [{date, equity}, ...],
            error: str | None,
            report_path: str | None,
        }
    """
    if cfg.timeout_sec is None:
        cfg.timeout_sec = config.backtest_timeout_sec

    # Generate tester.ini
    ini_path = _generate_tester_ini(cfg)

    # MT5 puts the report directly under the terminal data folder root
    # (not under Tester/Reports as one might expect). With Report=NAME in the
    # ini, the produced files are <data>/NAME.htm + <data>/NAME-*.png charts.
    reports_dir = config.resolve_mql5_dir().parent
    # Clear old reports to avoid mistaking a stale one for the new run
    for ext in (".htm", ".html", ".xml"):
        stale = reports_dir / f"{cfg.expert_name}_report{ext}"
        if stale.exists():
            stale.unlink()

    # Run terminal in tester mode.
    # NOTE: We deliberately omit /portable because /portable redirects MT5 to
    # use the install folder as the data dir, which won't contain the EA we
    # just compiled into the AppData instance. Without /portable, terminal64
    # uses the same data folder (AppData/Roaming/MetaQuotes/Terminal/<hash>)
    # where we wrote and compiled the EA.
    cmd = [
        str(config.terminal_path),
        f"/config:{ini_path}",
    ]
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            timeout=cfg.timeout_sec,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Backtest exceeded timeout ({cfg.timeout_sec}s)",
            "stats": None,
            "trades": [],
            "equity_curve": [],
            "report_path": None,
            "elapsed_sec": time.time() - start,
        }

    elapsed = time.time() - start

    # Find the generated report (XML preferred)
    report_path = _find_latest_report(reports_dir, cfg.expert_name)
    if report_path is None:
        return {
            "success": False,
            "error": "No backtest report generated",
            "stats": None,
            "trades": [],
            "equity_curve": [],
            "report_path": None,
            "stderr": proc.stderr,
            "elapsed_sec": elapsed,
        }

    # Parse the report
    parsed = parse_backtest_report(report_path)
    return {
        "success": True,
        "stats": parsed.get("stats"),
        "trades": parsed.get("trades", []),
        "equity_curve": parsed.get("equity_curve", []),
        "error": None,
        "report_path": str(report_path),
        "elapsed_sec": elapsed,
        "ini_used": str(ini_path),
    }


def _generate_tester_ini(cfg: BacktestConfig) -> Path:
    """Generate the tester.ini file from a BacktestConfig."""
    # Place ini in MT5 root tester folder
    tester_dir = config.reports_dir()
    tester_dir.mkdir(parents=True, exist_ok=True)
    ini_path = tester_dir / f"backtest_{cfg.expert_name}_{int(time.time())}.ini"

    # Format dates
    from_date = datetime.fromisoformat(cfg.from_date).strftime("%Y.%m.%d")
    to_date = datetime.fromisoformat(cfg.to_date).strftime("%Y.%m.%d")

    # Section [Tester]
    # NOTE: The Expert= field is interpreted RELATIVE to MQL5/Experts/, so do
    # NOT prefix with "Experts\". Adding it produces "Experts\Experts\X.ex5
    # not found" in the tester log (silent failure — terminal exits clean).
    tester_section = (
        f"Expert={cfg.expert_name}.ex5\n"
        f"Symbol={cfg.symbol}\n"
        f"Period={cfg.timeframe.upper()}\n"
        f"Optimization=0\n"
        f"Model={MODEL_CODES[cfg.model]}\n"
        f"FromDate={from_date}\n"
        f"ToDate={to_date}\n"
        f"ForwardMode=0\n"
        f"Deposit={cfg.deposit}\n"
        f"Currency={cfg.currency}\n"
        f"Leverage={cfg.leverage}\n"
        f"ExecutionMode=0\n"
        f"ProfitInPips=0\n"
        f"ShutdownTerminal=1\n"
        f"Visual={1 if cfg.visual else 0}\n"
        f"Report={cfg.expert_name}_report\n"
        f"ReplaceReport=1\n"
    )

    # Section [TesterInputs] — EA inputs
    inputs_section = ""
    if cfg.inputs:
        inputs_section = "[TesterInputs]\n"
        for key, value in cfg.inputs.items():
            inputs_section += f"{key}={value}\n"

    content = f"[Tester]\n{tester_section}\n{inputs_section}"
    ini_path.write_text(content, encoding="utf-16-le")
    return ini_path


def _find_latest_report(reports_dir: Path, expert_name: str) -> Optional[Path]:
    """Find the most recent report file for the given EA.

    Searches both <reports_dir>/ (MT5's default location for Report=NAME) and
    <reports_dir>/Reports/ (older builds + manual configurations).
    """
    search_dirs = [reports_dir, reports_dir / "Reports"]
    for ext in (".xml", ".html", ".htm"):
        candidates: list[Path] = []
        for d in search_dirs:
            if d.exists():
                # Match both NAME_report.ext and NAME-something.ext but skip
                # the chart PNGs and the auxiliary -holding/-hst/-mfemae files.
                for f in d.glob(f"{expert_name}_report{ext}"):
                    candidates.append(f)
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    return None

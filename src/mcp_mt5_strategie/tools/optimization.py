"""
Optimization — wraps MT5's native genetic/brute-force optimizer.

Allows running an EA across a grid of parameters and ranking results
by a chosen criterion (profit, Sharpe, custom).

THIS IS NEW — not in Qoyyuum's base server.
"""
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from ..config import config
from ..parsers.opt_xml import parse_optimization_report
from .backtest import BacktestConfig, MODEL_CODES, _find_latest_report, _stop_running_terminals

OptCriterion = Literal[
    "balance_max",
    "profit_factor_max",
    "expected_payoff_max",
    "drawdown_min",
    "recovery_factor_max",
    "sharpe_ratio_max",
    "custom",
]
OPT_CRITERION_CODES = {
    "balance_max": 0,
    "profit_factor_max": 1,
    "expected_payoff_max": 2,
    "drawdown_min": 3,
    "recovery_factor_max": 4,
    "sharpe_ratio_max": 5,
    "custom": 6,
}

OptAlgorithm = Literal["complete", "genetic"]
OPT_ALGO_CODES = {
    "complete": 1,  # brute-force on all combinations
    "genetic": 2,   # MT5 genetic algorithm
}


class ParamRange(BaseModel):
    """Parameter optimization range."""
    start: float
    step: float
    stop: float


class OptimizationConfig(BaseModel):
    """Configuration for an optimization run."""
    symbol: str
    timeframe: str = "H1"
    expert_name: str
    from_date: str
    to_date: str
    model: str = "1m_ohlc"  # default for opt = faster
    deposit: float = 100_000.0
    leverage: int = 100
    currency: str = "USD"

    # Optimization-specific
    criterion: OptCriterion = "sharpe_ratio_max"
    algorithm: OptAlgorithm = "genetic"

    # Parameters to optimize : {name: ParamRange or fixed_value}
    inputs: dict[str, Any] = Field(default_factory=dict)
    # For each input, if dict has {start, step, stop} → optimized, else fixed

    # Forward test split
    forward_mode: Literal["none", "half", "third", "quarter", "custom"] = "none"
    forward_date: Optional[str] = None  # required if forward_mode=custom

    timeout_sec: Optional[int] = None


def run_optimization(cfg: OptimizationConfig) -> dict:
    """Run a parameter optimization in MT5 Strategy Tester.

    Returns:
        {
            success: bool,
            passes: int,             # number of param combinations tested
            best_params: dict,
            best_stats: dict,
            all_passes: [
                {params: {...}, stats: {...}},
                ...
            ],
            error: str | None,
        }
    """
    if cfg.timeout_sec is None:
        cfg.timeout_sec = config.optimization_timeout_sec

    ini_path = _generate_optimizer_ini(cfg)

    reports_dir = config.reports_dir() / "Reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Clear old optimization report
    expected = reports_dir / f"{cfg.expert_name}_opt.xml"
    if expected.exists():
        expected.unlink()

    # Stop the bridge-terminal MT5 Python API may have launched (see backtest.py)
    try:
        import MetaTrader5 as mt5  # type: ignore
        mt5.shutdown()
    except Exception:
        pass
    _stop_running_terminals(config.terminal_path)

    # See note in backtest.py — /portable would point MT5 at the install dir,
    # not the AppData instance where the EA lives.
    cmd = [str(config.terminal_path), f"/config:{ini_path}"]
    start = time.time()
    try:
        subprocess.run(cmd, timeout=cfg.timeout_sec, capture_output=True)
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Optimization timeout ({cfg.timeout_sec}s)",
            "passes": 0,
            "best_params": None,
            "best_stats": None,
            "all_passes": [],
        }

    # Same as backtest : if MT5 is already running, subprocess returns instantly
    # while the actual test runs in the background. Poll for the report file.
    def _find_opt(name: str):
        r = _find_latest_report(reports_dir, f"{name}_opt")
        if r is None:
            r = _find_latest_report(reports_dir, name)
        return r

    report = _find_opt(cfg.expert_name)
    if report is None:
        deadline = start + cfg.timeout_sec
        while time.time() < deadline:
            time.sleep(5)
            report = _find_opt(cfg.expert_name)
            if report is not None:
                time.sleep(2)  # let MT5 finish writing
                report = _find_opt(cfg.expert_name)
                break

    if report is None:
        return {
            "success": False,
            "error": "No optimization report generated",
            "passes": 0,
            "best_params": None,
            "best_stats": None,
            "all_passes": [],
        }

    parsed = parse_optimization_report(report)
    # Find best by criterion
    best = _find_best(parsed["passes"], cfg.criterion)
    return {
        "success": True,
        "passes": len(parsed["passes"]),
        "best_params": best.get("params") if best else None,
        "best_stats": best.get("stats") if best else None,
        "all_passes": parsed["passes"],
        "report_path": str(report),
        "elapsed_sec": time.time() - start,
    }


def _generate_optimizer_ini(cfg: OptimizationConfig) -> Path:
    """Generate the tester.ini for optimization mode."""
    tester_dir = config.reports_dir()
    tester_dir.mkdir(parents=True, exist_ok=True)
    ini_path = tester_dir / f"opt_{cfg.expert_name}_{int(time.time())}.ini"

    from_date = datetime.fromisoformat(cfg.from_date).strftime("%Y.%m.%d")
    to_date = datetime.fromisoformat(cfg.to_date).strftime("%Y.%m.%d")

    fwd_codes = {"none": 0, "half": 1, "third": 2, "quarter": 4, "custom": 3}

    # Expert= is relative to MQL5/Experts/ — no "Experts\" prefix (see backtest.py)
    tester = (
        f"Expert={cfg.expert_name}.ex5\n"
        f"Symbol={cfg.symbol}\n"
        f"Period={cfg.timeframe.upper()}\n"
        f"Optimization={OPT_ALGO_CODES[cfg.algorithm]}\n"
        f"OptimizationCriterion={OPT_CRITERION_CODES[cfg.criterion]}\n"
        f"Model={MODEL_CODES[cfg.model]}\n"
        f"FromDate={from_date}\n"
        f"ToDate={to_date}\n"
        f"ForwardMode={fwd_codes[cfg.forward_mode]}\n"
    )
    if cfg.forward_mode == "custom" and cfg.forward_date:
        fwd = datetime.fromisoformat(cfg.forward_date).strftime("%Y.%m.%d")
        tester += f"ForwardDate={fwd}\n"
    tester += (
        f"Deposit={cfg.deposit}\n"
        f"Currency={cfg.currency}\n"
        f"Leverage={cfg.leverage}\n"
        f"ExecutionMode=0\n"
        f"ShutdownTerminal=1\n"
        f"Visual=0\n"
        f"Report={cfg.expert_name}_opt\n"
        f"ReplaceReport=1\n"
    )

    # TesterInputs section : encode ranges as MT5 expects
    # Format : InputName=start||start||step||stop||Y
    # Y at end = 1 to include in optimization, 0 to fix at value
    inputs_section = "[TesterInputs]\n"
    for name, val in cfg.inputs.items():
        if isinstance(val, dict) and "start" in val and "stop" in val:
            r = ParamRange(**val)
            inputs_section += f"{name}={r.start}||{r.start}||{r.step}||{r.stop}||Y\n"
        else:
            inputs_section += f"{name}={val}||{val}||0||0||N\n"

    content = f"[Tester]\n{tester}\n{inputs_section}"
    ini_path.write_text(content, encoding="utf-16-le")
    return ini_path


def _find_best(passes: list[dict], criterion: OptCriterion) -> Optional[dict]:
    """Find the best pass based on criterion."""
    if not passes:
        return None
    key_map = {
        "balance_max": ("profit", True),
        "profit_factor_max": ("profit_factor", True),
        "expected_payoff_max": ("expected_payoff", True),
        "drawdown_min": ("max_drawdown", False),
        "recovery_factor_max": ("recovery_factor", True),
        "sharpe_ratio_max": ("sharpe_ratio", True),
        "custom": ("custom_criterion", True),
    }
    key, reverse = key_map.get(criterion, ("profit", True))
    valid = [p for p in passes if key in p.get("stats", {})]
    if not valid:
        return None
    return sorted(valid, key=lambda p: p["stats"][key], reverse=reverse)[0]

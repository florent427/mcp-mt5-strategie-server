"""
Optimization — grid search over EA parameters with optional walk-forward.

DESIGN NOTE — why we don't use MT5's native optimizer
-----------------------------------------------------
MT5's native Strategy Tester optimization runs 16-core in parallel and is very
fast, but it writes results only to an undocumented binary cache file
(``Tester/cache/*.opt``) — not to XML or HTML. The .opt format has changed
between builds (5660 → 5833) and reverse-engineering it is fragile.

Instead we loop ``run_backtest`` in Python : slower (one core, no parallelism)
but every pass writes a parseable HTML report and we already validated that
end-to-end. Trade-off : ~25s × N combinations vs ~5min/100 native.

The native helpers (``_generate_optimizer_ini``, ``OPT_*_CODES``) are kept
for advanced users who want to drive MT5 manually and read the .opt cache
themselves.
"""
import itertools
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from ..config import config
from .backtest import BacktestConfig, MODEL_CODES, run_backtest

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
    "complete": 1,
    "genetic": 2,
}

# Map our optimization criterion → stat key produced by the HTML parser.
_CRITERION_TO_STAT = {
    "balance_max": ("net_profit", True),         # True = higher is better
    "profit_factor_max": ("profit_factor", True),
    "expected_payoff_max": ("expected_payoff", True),
    "drawdown_min": ("max_drawdown", False),     # False = lower is better
    "recovery_factor_max": ("recovery_factor", True),
    "sharpe_ratio_max": ("sharpe_ratio", True),
    "custom": ("net_profit", True),
}


class ParamRange(BaseModel):
    """Parameter optimization range (inclusive both ends)."""
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
    model: str = "1m_ohlc"  # faster model = better for grid search
    deposit: float = 100_000.0
    leverage: int = 100
    currency: str = "USD"

    criterion: OptCriterion = "sharpe_ratio_max"
    algorithm: OptAlgorithm = "genetic"  # kept for API parity, ignored by loop

    # {name: ParamRange dict or fixed value}
    inputs: dict[str, Any] = Field(default_factory=dict)

    # Walk-forward split
    forward_mode: Literal["none", "half", "third", "quarter", "custom"] = "none"
    forward_date: Optional[str] = None

    # Overall budget for the whole optimization (not per-backtest)
    timeout_sec: Optional[int] = None


# ============================================================
# Public entry point
# ============================================================

def run_optimization(cfg: OptimizationConfig) -> dict:
    """Grid-search optimization with optional walk-forward validation.

    For each parameter combination, runs a full backtest via ``run_backtest``
    (HTML report → parsed stats). Aggregates results, picks the best by the
    chosen criterion, and if ``forward_mode`` ≠ ``none`` re-runs the best
    params on the out-of-sample window to detect overfitting.

    Returns:
        {
            success: bool,
            passes: int,
            best_params: dict | None,
            best_stats: dict | None,
            all_passes: [{params, stats, success}, ...],
            train_window: (str, str),
            forward_window: (str, str) | None,
            forward_stats: dict | None,
            walk_forward_dropoff_pct: float | None,  # negative = worse OOS
            elapsed_sec: float,
            error: str | None,
        }
    """
    if cfg.timeout_sec is None:
        cfg.timeout_sec = config.optimization_timeout_sec
    start = time.time()

    train_window, forward_window = _split_walk_forward(cfg)
    ranges, fixed = _split_inputs(cfg.inputs)

    if not ranges:
        return _err("No optimization ranges provided (all params fixed)", start)

    # Build combinations as ordered list of (param_name → value) dicts
    keys = list(ranges.keys())
    value_lists = [ranges[k] for k in keys]
    combinations = list(itertools.product(*value_lists))

    # Run each combination on the training window
    all_passes: list[dict] = []
    for combo in combinations:
        if time.time() - start > cfg.timeout_sec:
            return _err(
                f"Optimization timeout — completed {len(all_passes)}/"
                f"{len(combinations)} passes",
                start,
                all_passes,
            )
        params = {**fixed, **dict(zip(keys, combo))}
        bt_cfg = BacktestConfig(
            symbol=cfg.symbol,
            timeframe=cfg.timeframe,
            expert_name=cfg.expert_name,
            from_date=train_window[0],
            to_date=train_window[1],
            model=cfg.model,
            deposit=cfg.deposit,
            leverage=cfg.leverage,
            currency=cfg.currency,
            inputs=params,
            visual=False,
        )
        try:
            result = run_backtest(bt_cfg)
        except Exception as e:  # noqa: BLE001
            all_passes.append({
                "params": params,
                "stats": {},
                "success": False,
                "error": f"{type(e).__name__}: {e}",
            })
            continue
        all_passes.append({
            "params": params,
            "stats": result.get("stats") or {},
            "success": bool(result.get("success")),
        })

    # Pick best on training window
    best = _find_best(all_passes, cfg.criterion)

    # Walk-forward validation
    forward_stats: Optional[dict] = None
    dropoff: Optional[float] = None
    if forward_window is not None and best is not None:
        fwd_cfg = BacktestConfig(
            symbol=cfg.symbol,
            timeframe=cfg.timeframe,
            expert_name=cfg.expert_name,
            from_date=forward_window[0],
            to_date=forward_window[1],
            model=cfg.model,
            deposit=cfg.deposit,
            leverage=cfg.leverage,
            currency=cfg.currency,
            inputs=best["params"],
            visual=False,
        )
        fwd_result = run_backtest(fwd_cfg)
        forward_stats = fwd_result.get("stats") or {}
        crit_key, _higher_better = _CRITERION_TO_STAT.get(
            cfg.criterion, ("net_profit", True)
        )
        train_v = best["stats"].get(crit_key)
        fwd_v = forward_stats.get(crit_key)
        if isinstance(train_v, (int, float)) and isinstance(fwd_v, (int, float)) and train_v:
            dropoff = (fwd_v - train_v) / abs(train_v) * 100.0

    return {
        "success": True,
        "passes": len(all_passes),
        "best_params": best["params"] if best else None,
        "best_stats": best["stats"] if best else None,
        "all_passes": all_passes,
        "train_window": list(train_window),
        "forward_window": list(forward_window) if forward_window else None,
        "forward_stats": forward_stats,
        "walk_forward_dropoff_pct": dropoff,
        "elapsed_sec": time.time() - start,
        "error": None,
    }


# ============================================================
# Helpers : input splitting, walk-forward, best selection
# ============================================================

def _split_inputs(inputs: dict[str, Any]) -> tuple[dict[str, list[float]], dict[str, Any]]:
    """Separate range-typed inputs from fixed-value inputs.

    Range dicts have at least ``start`` and ``stop``; everything else is fixed.
    Returns ``(ranges: {name: [values]}, fixed: {name: value})``.
    """
    ranges: dict[str, list[float]] = {}
    fixed: dict[str, Any] = {}
    for name, val in inputs.items():
        if isinstance(val, dict) and "start" in val and "stop" in val:
            r = ParamRange(**val)
            values = _range_values(r)
            ranges[name] = values
        else:
            fixed[name] = val
    return ranges, fixed


def _range_values(r: ParamRange) -> list[float]:
    """Inclusive range expansion. Handles float step error gracefully."""
    if r.step <= 0:
        return [r.start]
    out: list[float] = []
    v = r.start
    # Tolerance so 0.5 + 0.4 + 0.4 → includes 1.3 not just 0.9
    while v <= r.stop + r.step * 1e-9:
        # Round if step is integer-like
        if r.step == int(r.step) and r.start == int(r.start):
            out.append(int(round(v)))
        else:
            out.append(round(v, 8))
        v += r.step
    return out


def _split_walk_forward(
    cfg: OptimizationConfig,
) -> tuple[tuple[str, str], Optional[tuple[str, str]]]:
    """Compute (train_window, forward_window) from cfg.forward_mode."""
    start = datetime.fromisoformat(cfg.from_date)
    end = datetime.fromisoformat(cfg.to_date)
    span = end - start
    fmt = "%Y-%m-%d"

    if cfg.forward_mode == "none":
        return (cfg.from_date, cfg.to_date), None

    if cfg.forward_mode == "half":
        split = start + span / 2
    elif cfg.forward_mode == "third":
        split = start + span / 3
    elif cfg.forward_mode == "quarter":
        split = start + span / 4
    elif cfg.forward_mode == "custom":
        if not cfg.forward_date:
            raise ValueError("forward_date required when forward_mode='custom'")
        split = datetime.fromisoformat(cfg.forward_date)
    else:
        return (cfg.from_date, cfg.to_date), None

    train = (cfg.from_date, split.strftime(fmt))
    forward = (split.strftime(fmt), cfg.to_date)
    return train, forward


def _find_best(passes: list[dict], criterion: OptCriterion) -> Optional[dict]:
    """Pick the pass with the best stat for the given criterion."""
    if not passes:
        return None
    key, higher_better = _CRITERION_TO_STAT.get(criterion, ("net_profit", True))
    valid = [
        p for p in passes
        if isinstance(p.get("stats", {}).get(key), (int, float))
    ]
    if not valid:
        return None
    return sorted(valid, key=lambda p: p["stats"][key], reverse=higher_better)[0]


def _err(msg: str, start: float, all_passes: Optional[list] = None) -> dict:
    return {
        "success": False,
        "error": msg,
        "passes": len(all_passes) if all_passes else 0,
        "best_params": None,
        "best_stats": None,
        "all_passes": all_passes or [],
        "train_window": None,
        "forward_window": None,
        "forward_stats": None,
        "walk_forward_dropoff_pct": None,
        "elapsed_sec": time.time() - start,
    }


# ============================================================
# Native MT5 optimizer helpers — kept for advanced users
# ============================================================

def _generate_optimizer_ini(cfg: OptimizationConfig) -> Path:
    """Build a tester.ini for MT5's native optimizer.

    Kept for users who want to invoke MT5 directly and parse the .opt cache
    themselves. run_optimization() above does NOT use this — it loops
    run_backtest in Python.
    """
    tester_dir = config.reports_dir()
    tester_dir.mkdir(parents=True, exist_ok=True)
    ini_path = tester_dir / f"opt_{cfg.expert_name}_{int(time.time())}.ini"

    from_date = datetime.fromisoformat(cfg.from_date).strftime("%Y.%m.%d")
    to_date = datetime.fromisoformat(cfg.to_date).strftime("%Y.%m.%d")
    fwd_codes = {"none": 0, "half": 1, "third": 2, "quarter": 4, "custom": 3}

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

"""
Tests for optimization helper logic (no MT5 required).

Covers :
- _find_best : ranks passes by chosen criterion in correct order
- _range_values : inclusive range expansion with float-tolerant step
- _split_walk_forward : train/forward window math
- _split_inputs : separate ranges from fixed values
"""
from __future__ import annotations

import pytest

from mcp_mt5_strategie.tools.optimization import (
    OptimizationConfig,
    ParamRange,
    _find_best,
    _range_values,
    _split_inputs,
    _split_walk_forward,
)


PASSES = [
    {"pass_id": 1, "params": {"Lookback": 10}, "stats": {"net_profit": 500, "profit_factor": 1.15, "sharpe_ratio": 0.85, "max_drawdown": 800}},
    {"pass_id": 2, "params": {"Lookback": 20}, "stats": {"net_profit": 1500, "profit_factor": 1.72, "sharpe_ratio": 1.43, "max_drawdown": 1250}},
    {"pass_id": 3, "params": {"Lookback": 50}, "stats": {"net_profit": 800, "profit_factor": 1.45, "sharpe_ratio": 1.10, "max_drawdown": 950}},
]


def test_find_best_sharpe():
    best = _find_best(PASSES, "sharpe_ratio_max")
    assert best["params"]["Lookback"] == 20


def test_find_best_profit_factor():
    best = _find_best(PASSES, "profit_factor_max")
    assert best["params"]["Lookback"] == 20


def test_find_best_balance_max_uses_net_profit():
    """balance_max criterion should pick the highest net_profit."""
    best = _find_best(PASSES, "balance_max")
    assert best["params"]["Lookback"] == 20  # 1500 > 800 > 500


def test_find_best_drawdown_min():
    best = _find_best(PASSES, "drawdown_min")
    assert best["params"]["Lookback"] == 10


def test_find_best_empty():
    assert _find_best([], "sharpe_ratio_max") is None


def test_find_best_missing_key():
    bad = [{"stats": {"net_profit": 100}}]
    assert _find_best(bad, "sharpe_ratio_max") is None


# ============================================================
# Range expansion
# ============================================================

def test_range_values_integer():
    r = ParamRange(start=10, step=10, stop=50)
    assert _range_values(r) == [10, 20, 30, 40, 50]


def test_range_values_float_inclusive():
    """0.5 → 0.9 with step 0.1 must include both ends despite float error."""
    r = ParamRange(start=0.5, step=0.1, stop=0.9)
    out = _range_values(r)
    assert out[0] == 0.5
    assert out[-1] == 0.9
    assert len(out) == 5


def test_range_values_zero_step_returns_start_only():
    r = ParamRange(start=20, step=0, stop=50)
    assert _range_values(r) == [20]


# ============================================================
# Input splitting
# ============================================================

def test_split_inputs_separates_ranges_from_fixed():
    inputs = {
        "Lookback": {"start": 10, "step": 10, "stop": 50},
        "FibLevel": 0.9,
        "LongOnly": True,
    }
    ranges, fixed = _split_inputs(inputs)
    assert list(ranges.keys()) == ["Lookback"]
    assert ranges["Lookback"] == [10, 20, 30, 40, 50]
    assert fixed == {"FibLevel": 0.9, "LongOnly": True}


# ============================================================
# Walk-forward windows
# ============================================================

def test_walk_forward_none():
    cfg = OptimizationConfig(
        symbol="X", expert_name="E", from_date="2025-01-01", to_date="2025-12-31",
        inputs={}, forward_mode="none",
    )
    train, forward = _split_walk_forward(cfg)
    assert train == ("2025-01-01", "2025-12-31")
    assert forward is None


def test_walk_forward_half():
    cfg = OptimizationConfig(
        symbol="X", expert_name="E", from_date="2025-01-01", to_date="2025-12-31",
        inputs={}, forward_mode="half",
    )
    train, forward = _split_walk_forward(cfg)
    # 365 days / 2 → split around July 2
    assert train[0] == "2025-01-01"
    assert forward[1] == "2025-12-31"
    assert train[1] == forward[0]  # contiguous, no gap


def test_walk_forward_custom_requires_date():
    cfg = OptimizationConfig(
        symbol="X", expert_name="E", from_date="2025-01-01", to_date="2025-12-31",
        inputs={}, forward_mode="custom", forward_date=None,
    )
    with pytest.raises(ValueError, match="forward_date required"):
        _split_walk_forward(cfg)


def test_walk_forward_custom_uses_date():
    cfg = OptimizationConfig(
        symbol="X", expert_name="E", from_date="2025-01-01", to_date="2025-12-31",
        inputs={}, forward_mode="custom", forward_date="2025-09-01",
    )
    train, forward = _split_walk_forward(cfg)
    assert train == ("2025-01-01", "2025-09-01")
    assert forward == ("2025-09-01", "2025-12-31")

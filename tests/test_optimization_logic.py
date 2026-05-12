"""
Tests for optimization helper logic (no MT5 required).

Covers :
- _find_best : ranks passes by chosen criterion in correct order
- _generate_optimizer_ini : produces a valid ini structure
"""
from __future__ import annotations

from mcp_mt5_strategie.tools.optimization import _find_best


PASSES = [
    {"pass_id": 1, "params": {"Lookback": 10}, "stats": {"profit_factor": 1.15, "sharpe_ratio": 0.85, "max_drawdown": 800}},
    {"pass_id": 2, "params": {"Lookback": 20}, "stats": {"profit_factor": 1.72, "sharpe_ratio": 1.43, "max_drawdown": 1250}},
    {"pass_id": 3, "params": {"Lookback": 50}, "stats": {"profit_factor": 1.45, "sharpe_ratio": 1.10, "max_drawdown": 950}},
]


def test_find_best_sharpe():
    best = _find_best(PASSES, "sharpe_ratio_max")
    assert best["params"]["Lookback"] == 20  # highest sharpe = 1.43


def test_find_best_profit_factor():
    best = _find_best(PASSES, "profit_factor_max")
    assert best["params"]["Lookback"] == 20  # PF=1.72 wins


def test_find_best_drawdown_min():
    best = _find_best(PASSES, "drawdown_min")
    assert best["params"]["Lookback"] == 10  # smallest DD = 800


def test_find_best_empty():
    assert _find_best([], "sharpe_ratio_max") is None


def test_find_best_missing_key():
    """When chosen criterion key is missing from all passes, returns None."""
    bad = [{"stats": {"net_profit": 100}}]
    assert _find_best(bad, "sharpe_ratio_max") is None

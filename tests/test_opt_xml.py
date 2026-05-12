"""Tests for the optimization report parser."""
from __future__ import annotations

from pathlib import Path

from mcp_mt5_strategie.parsers.opt_xml import parse_optimization_report


def test_parse_returns_passes_count(opt_report: Path):
    result = parse_optimization_report(opt_report)
    assert result["total_passes"] == 3
    assert len(result["passes"]) == 3


def test_pass_ids_parsed(opt_report: Path):
    result = parse_optimization_report(opt_report)
    ids = [p["pass_id"] for p in result["passes"]]
    assert ids == [1, 2, 3]


def test_pass_params_extracted(opt_report: Path):
    result = parse_optimization_report(opt_report)
    passes = result["passes"]
    assert passes[0]["params"]["Lookback"] == 10.0
    assert passes[1]["params"]["Lookback"] == 20.0
    assert passes[2]["params"]["Lookback"] == 50.0


def test_pass_stats_extracted(opt_report: Path):
    result = parse_optimization_report(opt_report)
    passes = result["passes"]
    assert passes[0]["stats"]["net_profit"] == 1200.0
    assert passes[1]["stats"]["net_profit"] == 5234.50
    assert passes[2]["stats"]["net_profit"] == 3100.0
    # Sharpe extracted for ranking
    assert passes[1]["stats"]["sharpe_ratio"] == 1.43


def test_missing_file(tmp_path: Path):
    result = parse_optimization_report(tmp_path / "nope.xml")
    assert "error" in result
    assert result["passes"] == []

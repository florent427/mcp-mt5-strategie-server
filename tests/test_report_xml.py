"""Tests for the backtest report parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from mcp_mt5_strategie.parsers.report_xml import parse_backtest_report


def test_parse_returns_error_on_missing_file(missing_report: Path):
    result = parse_backtest_report(missing_report)
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_parse_xml_extracts_header(xml_report: Path):
    result = parse_backtest_report(xml_report)
    header = result["header"]
    assert header["symbol"] == "BTCUSD"
    assert header["period"] == "M5"
    assert header["expert"] == "FibEA"
    assert header["fromdate"] == "2025.01.01"
    assert header["todate"] == "2025.06.01"


def test_parse_xml_extracts_inputs(xml_report: Path):
    result = parse_backtest_report(xml_report)
    inputs = result["inputs"]
    assert inputs["Lookback"] == 20.0
    assert inputs["FibLevel"] == 0.9
    assert inputs["LotSize"] == 0.1


def test_parse_xml_extracts_stats(xml_report: Path):
    result = parse_backtest_report(xml_report)
    stats = result["stats"]
    assert stats["net_profit"] == 5234.50
    assert stats["profit_factor"] == 1.72
    assert stats["sharpe_ratio"] == 1.43
    assert stats["max_drawdown"] == 1250.00
    assert stats["trades"] == 187
    assert stats["win_trades"] == 102
    assert stats["loss_trades"] == 85
    assert stats["winrate"] == 54.55


def test_parse_xml_extracts_trades(xml_report: Path):
    result = parse_backtest_report(xml_report)
    trades = result["trades"]
    assert len(trades) == 3
    assert trades[0]["symbol"] == "BTCUSD"
    assert trades[0]["type"] == "buy"
    assert trades[0]["ticket"] == "100001"


def test_parse_xml_extracts_equity(xml_report: Path):
    result = parse_backtest_report(xml_report)
    eq = result["equity_curve"]
    assert len(eq) == 3
    assert eq[0]["balance"] == 100000.0
    assert eq[1]["equity"] == 100125.30


def test_parse_xml_utf8_fallback(xml_report_utf8: Path):
    """Some MT5 builds write UTF-8; parser must still work."""
    result = parse_backtest_report(xml_report_utf8)
    assert result["stats"]["net_profit"] == 5234.50


def test_parse_html_fallback(html_report: Path):
    """If file isn't valid XML, parser falls back to HTML."""
    result = parse_backtest_report(html_report)
    stats = result["stats"]
    assert stats["net_profit"] == 5234.50
    assert stats["profit_factor"] == 1.72
    assert stats["trades"] == 187


def test_parse_accepts_string_path(xml_report: Path):
    """parse_backtest_report should accept str as well as Path."""
    result = parse_backtest_report(str(xml_report))
    assert "stats" in result
    assert result["stats"]["net_profit"] == 5234.50

"""Tests for the config module — verifies env-var driven path resolution."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_mt5_strategie.config import MT5Config


def test_default_paths():
    cfg = MT5Config()
    # Should point to standard Windows MT5 install
    assert "MetaTrader 5" in str(cfg.terminal_path) or cfg.terminal_path.name == "terminal64.exe"
    assert cfg.metaeditor_path.name == "metaeditor64.exe"


def test_env_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MT5_TERMINAL_PATH", r"D:\custom\terminal64.exe")
    monkeypatch.setenv("MT5_METAEDITOR_PATH", r"D:\custom\metaeditor64.exe")
    cfg = MT5Config()
    assert cfg.terminal_path == Path(r"D:\custom\terminal64.exe")
    assert cfg.metaeditor_path == Path(r"D:\custom\metaeditor64.exe")


def test_default_timeouts():
    cfg = MT5Config()
    assert cfg.backtest_timeout_sec == 600
    assert cfg.compile_timeout_sec == 60
    assert cfg.optimization_timeout_sec == 7200


def test_resolve_mql5_dir_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """When data_path doesn't exist, resolve_mql5_dir raises FileNotFoundError."""
    monkeypatch.setenv("MT5_DATA_PATH", str(tmp_path / "nope"))
    cfg = MT5Config()
    with pytest.raises(FileNotFoundError):
        cfg.resolve_mql5_dir()


def test_resolve_mql5_dir_finds_subfolder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Sim a MT5 layout : <data>/<hash>/MQL5/."""
    instance = tmp_path / "ABCDEF1234567890"
    mql5 = instance / "MQL5"
    mql5.mkdir(parents=True)
    monkeypatch.setenv("MT5_DATA_PATH", str(tmp_path))
    cfg = MT5Config()
    assert cfg.resolve_mql5_dir() == mql5

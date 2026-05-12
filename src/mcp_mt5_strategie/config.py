"""
Configuration central — chemins MT5, timeouts, paramètres par défaut.
"""
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class MT5Config(BaseModel):
    """Configuration MT5 — paths and runtime."""

    terminal_path: Path = Field(
        default_factory=lambda: Path(
            os.environ.get("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
        )
    )
    metaeditor_path: Path = Field(
        default_factory=lambda: Path(
            os.environ.get("MT5_METAEDITOR_PATH", r"C:\Program Files\MetaTrader 5\metaeditor64.exe")
        )
    )
    data_path: Path = Field(
        default_factory=lambda: Path(
            os.environ.get(
                "MT5_DATA_PATH",
                str(Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal"),
            )
        )
    )
    mql5_dir: Optional[Path] = None  # rempli à l'initialisation
    backtest_timeout_sec: int = 600  # 10 min max par défaut
    compile_timeout_sec: int = 60
    optimization_timeout_sec: int = 7200  # 2h pour optimisation

    def resolve_mql5_dir(self) -> Path:
        """Find the MQL5 data folder that matches our terminal_path.

        Each MT5 install gets its own AppData/Roaming/MetaQuotes/Terminal/<hash>
        folder, identified by an origin.txt that contains the install dir path.
        Picking the wrong instance silently — as the previous "first match"
        heuristic did — means the EA is written to one folder but
        terminal64.exe runs from another, and no backtest ever fires.
        """
        if self.mql5_dir is not None and self.mql5_dir.exists():
            return self.mql5_dir
        if not self.data_path.exists():
            raise FileNotFoundError(f"MT5 data path not found: {self.data_path}")

        install_dir = str(self.terminal_path.parent).lower()
        fallback: Optional[Path] = None
        for sub in self.data_path.iterdir():
            mql5 = sub / "MQL5"
            if not mql5.is_dir():
                continue
            # MT5 writes origin.txt as UTF-16 LE with BOM
            origin = sub / "origin.txt"
            if origin.exists():
                try:
                    raw = origin.read_text(encoding="utf-16-le").strip().lstrip("﻿")
                except UnicodeDecodeError:
                    raw = origin.read_text(encoding="utf-8", errors="replace").strip()
                if raw.lower().startswith(install_dir):
                    self.mql5_dir = mql5
                    return mql5
            # Remember first viable folder in case nothing matches
            if fallback is None:
                fallback = mql5

        if fallback is not None:
            self.mql5_dir = fallback
            return fallback
        raise FileNotFoundError(f"No MQL5 directory found under {self.data_path}")

    def experts_dir(self) -> Path:
        return self.resolve_mql5_dir() / "Experts"

    def scripts_dir(self) -> Path:
        return self.resolve_mql5_dir() / "Scripts"

    def indicators_dir(self) -> Path:
        return self.resolve_mql5_dir() / "Indicators"

    def tester_dir(self) -> Path:
        return self.resolve_mql5_dir() / "Profiles" / "Tester"

    def reports_dir(self) -> Path:
        return self.resolve_mql5_dir().parent / "Tester"

    def logs_dir(self) -> Path:
        return self.resolve_mql5_dir().parent / "Logs"


# Singleton config
config = MT5Config()

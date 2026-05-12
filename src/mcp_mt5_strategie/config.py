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
        """Trouve le dossier MQL5 sous data_path/<instance_id>/MQL5."""
        if self.mql5_dir is not None and self.mql5_dir.exists():
            return self.mql5_dir
        if not self.data_path.exists():
            raise FileNotFoundError(f"MT5 data path not found: {self.data_path}")
        # data_path contient des sous-dossiers nommés par hash de terminal
        for sub in self.data_path.iterdir():
            mql5 = sub / "MQL5"
            if mql5.is_dir():
                self.mql5_dir = mql5
                return mql5
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

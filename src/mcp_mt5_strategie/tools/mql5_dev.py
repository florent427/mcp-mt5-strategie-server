"""
MQL5 development — write, compile, manage source files.

This module wraps:
  - File I/O in MT5's MQL5/Experts, MQL5/Scripts, MQL5/Indicators folders
  - MetaEditor CLI for compilation (metaeditor64.exe /compile)
  - Compile log parsing

THIS IS NEW — not in Qoyyuum's base server.
"""
import subprocess
from pathlib import Path
from typing import Literal

from ..config import config

MQL5Type = Literal["expert", "script", "indicator", "library"]


def _resolve_dir(file_type: MQL5Type) -> Path:
    """Map type → directory in MT5's MQL5 folder."""
    mapping = {
        "expert": config.experts_dir(),
        "script": config.scripts_dir(),
        "indicator": config.indicators_dir(),
        "library": config.resolve_mql5_dir() / "Libraries",
    }
    return mapping[file_type]


def write_mql5_file(filename: str, code: str, file_type: MQL5Type = "expert") -> dict:
    """Write a MQL5 source file (.mq5) to the appropriate MT5 folder.

    Args:
        filename: e.g. "MyEA.mq5" or "MyEA" (extension added if missing)
        code: full MQL5 source code
        file_type: "expert" (EA), "script", "indicator", "library"

    Returns:
        {success: bool, path: str, size_bytes: int}
    """
    if not filename.endswith(".mq5"):
        filename += ".mq5"

    target_dir = _resolve_dir(file_type)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename

    target.write_text(code, encoding="utf-8")
    return {
        "success": True,
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "file_type": file_type,
    }


def read_mql5_file(filename: str, file_type: MQL5Type = "expert") -> dict:
    """Read a MQL5 source file."""
    if not filename.endswith((".mq5", ".mqh")):
        filename += ".mq5"
    target_dir = _resolve_dir(file_type)
    target = target_dir / filename
    if not target.exists():
        return {"success": False, "error": f"File not found: {target}"}
    return {
        "success": True,
        "path": str(target),
        "code": target.read_text(encoding="utf-8"),
    }


def list_mql5_files(file_type: MQL5Type = "expert") -> list[dict]:
    """List all .mq5 and .ex5 files in the target directory."""
    target_dir = _resolve_dir(file_type)
    if not target_dir.exists():
        return []
    results = []
    for ext in ("*.mq5", "*.ex5"):
        for f in target_dir.glob(ext):
            results.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "modified": f.stat().st_mtime,
                "compiled": f.suffix == ".ex5",
            })
    return sorted(results, key=lambda x: x["name"])


def compile_mql5(filename: str, file_type: MQL5Type = "expert") -> dict:
    """Compile a MQL5 source file using MetaEditor CLI.

    The MetaEditor command:
        metaeditor64.exe /compile:"path/to/file.mq5" /log

    Generates path/to/file.log with errors/warnings.

    Returns:
        {
            success: bool,
            ex5_path: str | None,    # path to compiled .ex5 if success
            errors: [str],            # compilation errors
            warnings: [str],          # compilation warnings
            log: str,                 # raw log content
        }
    """
    if not filename.endswith(".mq5"):
        filename += ".mq5"
    target_dir = _resolve_dir(file_type)
    source = target_dir / filename
    if not source.exists():
        return {
            "success": False,
            "ex5_path": None,
            "errors": [f"Source file not found: {source}"],
            "warnings": [],
            "log": "",
        }

    log_path = source.with_suffix(".log")
    if log_path.exists():
        log_path.unlink()

    # Run MetaEditor compilation
    cmd = [
        str(config.metaeditor_path),
        f"/compile:{source}",
        "/log",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=config.compile_timeout_sec,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "ex5_path": None,
            "errors": ["Compilation timeout"],
            "warnings": [],
            "log": "",
        }

    # Parse the log file
    errors, warnings, raw_log = _parse_compile_log(log_path)
    ex5 = source.with_suffix(".ex5")
    success = ex5.exists() and len(errors) == 0

    return {
        "success": success,
        "ex5_path": str(ex5) if success else None,
        "errors": errors,
        "warnings": warnings,
        "log": raw_log,
        "exit_code": proc.returncode,
    }


def _parse_compile_log(log_path: Path) -> tuple[list[str], list[str], str]:
    """Parse MetaEditor compile log (UTF-16 LE typically).

    Format example :
        ConfigEA.mq5 : information: Checking '...'
        ConfigEA.mq5(42,5) : error 161: 'undeclared identifier'
        ConfigEA.mq5(50,3) : warning 167: 'unreachable code'
        Result: 1 errors, 1 warnings, 0 information messages
    """
    if not log_path.exists():
        return [], [], ""

    # MetaEditor logs are UTF-16 LE
    try:
        raw = log_path.read_text(encoding="utf-16-le")
    except UnicodeDecodeError:
        raw = log_path.read_text(encoding="utf-8", errors="replace")

    errors = []
    warnings = []
    for line in raw.splitlines():
        line = line.strip()
        if " error " in line.lower() or "error:" in line.lower():
            errors.append(line)
        elif " warning " in line.lower() or "warning:" in line.lower():
            warnings.append(line)
    return errors, warnings, raw

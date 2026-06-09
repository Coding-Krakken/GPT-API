from __future__ import annotations

import subprocess
from pathlib import Path

from utils.policy import ensure_under_allowed_root


def run_checked(argv: list[str], cwd: str | Path, timeout: int = 120) -> dict:
    cwd_path = ensure_under_allowed_root(cwd)
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "passed": result.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "exit_code": -1,
            "passed": False,
            "timeout": True,
        }
    except FileNotFoundError as exc:
        return {
            "stdout": "",
            "stderr": str(exc),
            "exit_code": 127,
            "passed": False,
            "not_found": True,
        }

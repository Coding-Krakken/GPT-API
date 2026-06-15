from __future__ import annotations

import subprocess
from pathlib import Path

from utils.policy import ensure_under_allowed_root
from utils import eval_telemetry


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
        out = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "passed": result.returncode == 0,
        }
        eval_telemetry.log_event("subprocess_completed", argv=argv, executable=argv[0] if argv else None, cwd=str(cwd_path), exit_code=result.returncode, passed=result.returncode == 0, timeout=False)
        return out
    except subprocess.TimeoutExpired as exc:
        out = {
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "exit_code": -1,
            "passed": False,
            "timeout": True,
        }
        eval_telemetry.log_event("subprocess_completed", argv=argv, executable=argv[0] if argv else None, cwd=str(cwd_path), exit_code=-1, passed=False, timeout=True)
        return out
    except FileNotFoundError as exc:
        out = {
            "stdout": "",
            "stderr": str(exc),
            "exit_code": 127,
            "passed": False,
            "not_found": True,
        }
        eval_telemetry.log_event("subprocess_completed", argv=argv, executable=argv[0] if argv else None, cwd=str(cwd_path), exit_code=127, passed=False, not_found=True)
        return out

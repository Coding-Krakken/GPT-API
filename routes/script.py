from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from utils.auth import verify_key
from utils.audit import redact_text

router = APIRouter()

_SCRIPT_SUFFIX = {
    "bash": ".sh",
    "sh": ".sh",
    "python": ".py",
    "node": ".js",
    "js": ".js",
    "javascript": ".js",
}

_SCRIPT_RUNNER = {
    "bash": ["bash"],
    "sh": ["sh"],
    "python": ["python"],
    "node": ["node"],
    "js": ["node"],
    "javascript": ["node"],
}


class ScriptRunRequest(BaseModel):
    language: str = Field(default="bash")
    content: str = Field(..., min_length=1, max_length=1_000_000)
    working_dir: Optional[str] = None
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    env: Optional[Dict[str, str]] = None
    stdin: Optional[str] = None
    argv: list[str] | None = None
    capture: bool = True
    max_output_bytes: int = Field(default=1048576, ge=1024, le=10485760)
    dry_run: bool = False
    keep_script: bool = False


def _meta(start: float, status: int = 200) -> dict:
    return {"status": status, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}


def _truncate_and_redact(text: str | None, max_bytes: int) -> tuple[str, int, bool]:
    text = redact_text(text or "") or ""
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text, len(raw), False
    return raw[:max_bytes].decode("utf-8", errors="replace") + "\n...output truncated", len(raw), True


def _resolve_working_dir(value: str | None) -> str | None:
    if not value:
        return None
    cwd = os.path.abspath(os.path.expanduser(value))
    if not os.path.isdir(cwd):
        raise ValueError(f"Working directory does not exist: {cwd}")
    return cwd


@router.post("/run", dependencies=[Depends(verify_key)])
def run_script(req: ScriptRunRequest):
    start = time.time()
    lang = req.language.lower()
    if lang not in _SCRIPT_RUNNER:
        return {"error": {"code": "unsupported_language", "message": f"language must be one of {sorted(_SCRIPT_RUNNER)}"}, **_meta(start, 400)}
    try:
        cwd = _resolve_working_dir(req.working_dir)
    except ValueError as exc:
        return {"error": {"code": "invalid_working_dir", "message": str(exc)}, **_meta(start, 400)}

    suffix = _SCRIPT_SUFFIX[lang]
    script_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=suffix, prefix="gpt_api_script_", delete=False, encoding="utf-8") as handle:
            handle.write(req.content)
            script_path = handle.name
        os.chmod(script_path, 0o700)
        command = _SCRIPT_RUNNER[lang] + [script_path] + (req.argv or [])
        if req.dry_run:
            return {"command": shlex.join(command), "script_path": script_path if req.keep_script else None, "dry_run": True, **_meta(start)}
        env = os.environ.copy()
        if req.env:
            env.update(req.env)
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            input=req.stdin,
            capture_output=req.capture,
            text=True,
            timeout=req.timeout_seconds,
        )
        stdout, stdout_bytes, stdout_truncated = _truncate_and_redact(result.stdout, req.max_output_bytes)
        stderr, stderr_bytes, stderr_truncated = _truncate_and_redact(result.stderr, req.max_output_bytes)
        status = 200 if result.returncode == 0 else 400
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": result.returncode,
            "command": shlex.join(command),
            "script_path": script_path if req.keep_script else None,
            "stdout_bytes": stdout_bytes,
            "stderr_bytes": stderr_bytes,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            **_meta(start, status),
        }
    except subprocess.TimeoutExpired as exc:
        return {"error": {"code": "timeout", "message": str(exc), "hint": "Use a shorter timeout or run long work via /shell action=start and poll job status."}, **_meta(start, 408)}
    except Exception as exc:
        return {"error": {"code": "script_execution_error", "message": str(exc)}, **_meta(start, 500)}
    finally:
        if script_path and not req.keep_script:
            try:
                Path(script_path).unlink(missing_ok=True)
            except Exception:
                pass

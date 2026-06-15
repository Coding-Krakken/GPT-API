from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import asyncio
import subprocess
import shutil
import re
import os
import time
import uuid
from utils.auth import verify_key
from utils.audit import log_api_action, redact_text
from utils.platform_tools import is_windows, translate_command_for_windows

router = APIRouter()
JOBS: Dict[str, dict] = {}


def redact_secrets(text: str) -> str:
    return redact_text(text) or ""


class ShellCommand(BaseModel):
    action: str = "run"
    command: str = ""
    job_id: Optional[str] = None
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    run_as_sudo: bool = False
    background: bool = False
    fault: Optional[str] = None
    shell: Optional[str] = None
    working_dir: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    stdin: Optional[str] = None
    capture: bool = True
    max_output_bytes: int = Field(default=1048576, ge=1024, le=10485760)
    allowed_exit_codes: List[int] = [0]
    dry_run: bool = False


def _meta(start: float, status: int = 200):
    return {"status": status, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}


def _truncate(text: str, max_bytes: int) -> str:
    raw = (text or "").encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text or ""
    return raw[:max_bytes].decode("utf-8", errors="replace") + "\n...output truncated"


def _shell_executable(shell: Optional[str]) -> Optional[str]:
    if shell:
        return (shutil.which(shell) or shell) if is_windows() and not os.path.isabs(shell) else shell
    return (shutil.which("powershell.exe") or shutil.which("cmd.exe")) if is_windows() else "/bin/bash"


def _prepare_command(data: ShellCommand) -> str:
    cmd = translate_command_for_windows(data.command) if is_windows() else data.command
    if data.run_as_sudo and not is_windows():
        cmd = f"sudo {cmd}"
    return cmd


@router.post("", dependencies=[Depends(verify_key)])
@router.post("/", dependencies=[Depends(verify_key)])
async def run_shell_command(data: ShellCommand, request: Request):
    start = time.time()

    def finish(resp: dict, status: int = 200):
        log_api_action(request, "/shell", "run_shell_command", status, str(resp))
        return resp

    try:
        action = (data.action or "run").lower()
        if data.background and action == "run":
            action = "start"
        if data.fault == "permission":
            return finish({"result": {"error": {"code": "permission_denied", "message": "Permission denied"}, "status": 403}, **_meta(start, 403)}, 403)
        if data.fault == "io":
            return finish({"result": {"error": {"code": "io_error", "message": "I/O error occurred"}, "status": 500}, **_meta(start, 500)}, 500)
        if action in ["status", "stop", "logs"]:
            if not data.job_id or data.job_id not in JOBS:
                return finish({"error": {"code": "unknown_job", "message": "Unknown or missing job_id"}, **_meta(start, 404)}, 404)
            job = JOBS[data.job_id]
            proc: subprocess.Popen = job["proc"]
            if action == "status":
                rc = proc.poll()
                return finish({"job_id": data.job_id, "pid": proc.pid, "running": rc is None, "exit_code": rc, **_meta(start)}, 200)
            if action == "stop":
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                return finish({"job_id": data.job_id, "pid": proc.pid, "running": proc.poll() is None, "exit_code": proc.poll(), **_meta(start)}, 200)
            stdout = stderr = ""
            if proc.poll() is not None and job.get("capture"):
                try:
                    out, err = proc.communicate(timeout=1)
                    stdout, stderr = out or "", err or ""
                except Exception:
                    pass
            return finish({"job_id": data.job_id, "pid": proc.pid, "stdout": redact_secrets(_truncate(stdout, data.max_output_bytes)), "stderr": redact_secrets(_truncate(stderr, data.max_output_bytes)), "exit_code": proc.poll(), **_meta(start)}, 200)
        if action not in ["run", "start"]:
            return finish({"result": {"error": {"code": "unsupported_action", "message": f"Unsupported shell action: {action}"}, "status": 400}, **_meta(start, 400)}, 400)
        if not data.command.strip():
            return finish({"result": {"error": {"code": "missing_command", "message": "Command cannot be empty"}, "status": 400}, **_meta(start, 400)}, 400)
        if len(data.command) > 4096:
            return finish({"result": {"error": {"code": "command_too_long", "message": "Command exceeds maximum allowed length (4096 characters).", "recommended_alternatives": ["write a script with /files then execute it", "use /code with content for Python/JS/Bash", "use /script/run for large scripts", "use /batch for multiple smaller operations"]}, "status": 400}, **_meta(start, 400)}, 400)
        cmd = _prepare_command(data)
        env = os.environ.copy()
        if data.env:
            env.update(data.env)
        cwd = os.path.abspath(os.path.expanduser(data.working_dir)) if data.working_dir else None
        if cwd and not os.path.isdir(cwd):
            return finish({"result": {"error": {"code": "invalid_working_dir", "message": f"Working directory does not exist: {cwd}"}, "status": 400}, **_meta(start, 400)}, 400)
        if data.dry_run:
            return finish({"command": cmd, "dry_run": True, **_meta(start)}, 200)
        shell_exe = _shell_executable(data.shell)
        if action == "start":
            proc = subprocess.Popen(cmd, shell=True, executable=shell_exe, cwd=cwd, env=env, stdin=subprocess.PIPE if data.stdin else None, stdout=subprocess.PIPE if data.capture else subprocess.DEVNULL, stderr=subprocess.PIPE if data.capture else subprocess.DEVNULL, text=True, start_new_session=not is_windows())
            if data.stdin and proc.stdin:
                try:
                    proc.stdin.write(data.stdin)
                    proc.stdin.close()
                except Exception:
                    pass
            job_id = str(uuid.uuid4())
            JOBS[job_id] = {"proc": proc, "command": cmd, "created": time.time(), "capture": data.capture}
            return finish({"stdout": "", "stderr": "", "exit_code": 0, "pid": proc.pid, "job_id": job_id, "background": True, **_meta(start)}, 200)
        result = await asyncio.to_thread(subprocess.run, cmd, shell=True, executable=shell_exe, cwd=cwd, env=env, input=data.stdin, capture_output=data.capture, text=True, timeout=data.timeout_seconds)
        status = 200 if result.returncode in data.allowed_exit_codes else 400
        return finish({"stdout": redact_secrets(_truncate(result.stdout or "", data.max_output_bytes)), "stderr": redact_secrets(_truncate(result.stderr or "", data.max_output_bytes)), "exit_code": result.returncode, "command": cmd, **_meta(start, status)}, status)
    except subprocess.TimeoutExpired as e:
        return finish({"result": {"error": {"code": "timeout", "message": str(e)}, "status": 408}, **_meta(start, 408)}, 408)
    except Exception as e:
        return finish({"result": {"error": {"code": "subprocess_error", "message": str(e)}, "status": 500}, **_meta(start, 500)}, 500)

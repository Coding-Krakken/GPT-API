from fastapi import APIRouter, HTTPException, Depends, Response, Request
from pydantic import BaseModel
import asyncio
import subprocess
import shlex
import shutil
import re
import os
import time
import platform
from utils.auth import verify_key
from utils.audit import log_api_action
from utils.platform_tools import is_windows, normalize_path, translate_command_for_windows

router = APIRouter()

def redact_secrets(text: str) -> str:
    # Redact common API key patterns
    patterns = [
        r"(API_KEY\s*=\s*)\S+",
        r"(OPENAI_API_KEY\s*=\s*)\S+",
        r"(sk-[a-zA-Z0-9]{20,})"
    ]
    for pat in patterns:
        text = re.sub(pat, r"\1[REDACTED]", text)
    return text


SSH_TIMEOUT_OPTIONS = [
    ("ConnectTimeout", "10"),
    ("ServerAliveInterval", "15"),
    ("ServerAliveCountMax", "2"),
    ("BatchMode", "yes"),
]

SHELL_META_CHARS = set('|&;<>()$`\\\n')

def add_ssh_timeouts(command: str) -> str:
    """Inject conservative OpenSSH timeout options into simple ssh commands.

    This intentionally only rewrites plain commands whose executable is ssh
    (optionally prefixed by sudo). Commands using shell metacharacters are left
    untouched to avoid changing complex shell semantics.
    """
    if not command or any(ch in command for ch in SHELL_META_CHARS):
        return command

    try:
        parts = shlex.split(command)
    except ValueError:
        return command

    if not parts:
        return command

    insert_at = None
    if parts[0] == "ssh":
        insert_at = 1
    elif parts[0] == "sudo" and len(parts) > 1 and parts[1] == "ssh":
        insert_at = 2
    else:
        return command

    existing_options = set()
    idx = insert_at
    while idx < len(parts):
        token = parts[idx]
        if token == "--":
            break
        if token == "-o" and idx + 1 < len(parts):
            existing_options.add(parts[idx + 1].split("=", 1)[0])
            idx += 2
            continue
        if token.startswith("-o") and len(token) > 2:
            existing_options.add(token[2:].split("=", 1)[0])
        idx += 1

    additions = []
    for key, value in SSH_TIMEOUT_OPTIONS:
        if key not in existing_options:
            additions.extend(["-o", f"{key}={value}"])

    if not additions:
        return command

    parts[insert_at:insert_at] = additions
    return shlex.join(parts)

class ShellCommand(BaseModel):
    command: str
    timeout_seconds: int = 300
    run_as_sudo: bool = False
    background: bool = False
    fault: str = None  # Optional fault injection
    shell: str = None  # Default shell is auto-detected

@router.post("/", dependencies=[Depends(verify_key)])
async def run_shell_command(data: ShellCommand, request: Request):
    start = time.time()
    if not data.command or not data.command.strip():
        resp = {
            "result": {
                "error": {"code": "missing_command", "message": "Command cannot be empty or whitespace."},
                "status": 400
            },
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000)
        }
        log_api_action(request, "/shell", "run_shell_command", 400, str(resp))
        return resp
    # Enforce max command length (4096 chars, as in OpenAPI schema)
    if len(data.command) > 4096:
        resp = {
                "result": {
                    "error": {"code": "command_too_long", "message": "Command exceeds maximum allowed length (4096 characters)."},
                    "status": 400
                },
                "latency_ms": round((time.time() - start) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        log_api_action(request, "/shell", "run_shell_command", 400, str(resp))
        return resp
    payload_size = len(data.command) if data.command else 0
    try:
        if data.fault == 'permission':
            resp = {
                "result": {
                    "error": {"code": "permission_denied", "message": "Permission denied"},
                    "status": 403
                },
                "latency_ms": round((time.time() - start) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
            log_api_action(request, "/shell", "run_shell_command", 403, str(resp))
            return resp
        if data.fault == 'io':
            resp = {
                "result": {
                    "error": {"code": "io_error", "message": "I/O error occurred"},
                    "status": 500
                },
                "latency_ms": round((time.time() - start) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
            log_api_action(request, "/shell", "run_shell_command", 500, str(resp))
            return resp


        # Windows compatibility: auto-detect shell and translate commands
        shell_executable = data.shell
        if not shell_executable:
            if is_windows():
                # Prefer PowerShell if available, else fallback to cmd.exe (absolute path)
                powershell_path = shutil.which("powershell.exe")
                cmd_path = shutil.which("cmd.exe")
                shell_executable = powershell_path or cmd_path or os.path.join(os.environ.get("SystemRoot", r"C:\\Windows"), "System32", "cmd.exe")
            else:
                shell_executable = "/bin/bash"
        else:
            # If shell_executable is not an absolute path on Windows, resolve via PATH
            if is_windows() and not os.path.isabs(shell_executable):
                resolved = shutil.which(shell_executable)
                if resolved:
                    shell_executable = resolved

        # --- Windows PATH resolution for command itself ---
        full_command = data.command
        if is_windows():
            import shlex
            # Only resolve the first word (the executable)
            parts = shlex.split(full_command, posix=False)
            if parts:
                exe = parts[0]
                # Only resolve if not an absolute path and not already quoted
                if not os.path.isabs(exe) and not (exe.startswith('"') or exe.startswith("'")):
                    resolved_exe = shutil.which(exe)
                    if resolved_exe:
                        parts[0] = resolved_exe
                        full_command = ' '.join(parts)
            full_command = translate_command_for_windows(full_command)
            # Sudo is not supported on Windows
        elif data.run_as_sudo:
            full_command = f"sudo {full_command}"


        full_command = data.command
        if is_windows():
            full_command = translate_command_for_windows(full_command)
            # Sudo is not supported on Windows
        elif data.run_as_sudo:
            full_command = f"sudo {full_command}"

        full_command = add_ssh_timeouts(full_command)

        latency = round((time.time() - start) * 1000, 2)
        headers = {"X-Payload-Size": str(payload_size), "X-Latency-ms": str(latency)}
        if data.background:
            proc = subprocess.Popen(
                full_command,
                shell=True,
                executable=shell_executable,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True
            )
            resp = {
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "pid": proc.pid,
                "background": True,
                "status": 200,
                "message": "Process started in background. Output is not captured for background commands.",
                "latency_ms": round((time.time() - start) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
            log_api_action(request, "/shell", "run_shell_command", 200, str(resp))
            return resp
        else:
            result = await asyncio.to_thread(
                subprocess.run,
                full_command,
                shell=True,
                executable=shell_executable,
                capture_output=True,
                text=True,
                timeout=min(data.timeout_seconds,3600)
            )
            resp = {
                "stdout": redact_secrets(result.stdout.strip()),
                "stderr": redact_secrets(result.stderr.strip()),
                "exit_code": result.returncode,
                "status": 200,
                "latency_ms": round((time.time() - start) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
            log_api_action(request, "/shell", "run_shell_command", 200, str(resp))
            return resp
    except Exception as e:
        resp = {
            "result": {
                "error": {"code": "subprocess_error", "message": str(e)},
                "status": 500
            },
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000)
        }
        log_api_action(request, "/shell", "run_shell_command", 500, str(resp))
        return resp

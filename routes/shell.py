from fastapi import APIRouter, HTTPException, Depends, Response, Request
from pydantic import BaseModel
import subprocess
import re
import os
from utils.auth import verify_key
from utils.audit import log_api_action

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

class ShellCommand(BaseModel):
    command: str
    run_as_sudo: bool = False
    background: bool = False
    fault: str = None  # Optional fault injection
    shell: str = "/bin/bash"  # Default shell for UNIX systems

@router.post("/", dependencies=[Depends(verify_key)])
async def run_shell_command(data: ShellCommand, request: Request):
    if not data.command or not data.command.strip():
        resp = {
            "result": {
                "error": {"code": "missing_command", "message": "Command cannot be empty or whitespace."},
                "status": 400
            }
        }
        log_api_action(request, "/shell", "run_shell_command", 400, str(resp))
        return resp
    # Enforce max command length (4096 chars, as in OpenAPI schema)
    if len(data.command) > 4096:
        resp = {
            "result": {
                "error": {"code": "command_too_long", "message": "Command exceeds maximum allowed length (4096 characters)."},
                "status": 400
            }
        }
        log_api_action(request, "/shell", "run_shell_command", 400, str(resp))
        return resp
    import time
    start = time.time()
    payload_size = len(data.command) if data.command else 0
    try:
        if data.fault == 'permission':
            resp = {
                "result": {
                    "error": {"code": "permission_denied", "message": "Permission denied"},
                    "status": 403
                }
            }
            log_api_action(request, "/shell", "run_shell_command", 403, str(resp))
            return resp
        if data.fault == 'io':
            resp = {
                "result": {
                    "error": {"code": "io_error", "message": "I/O error occurred"},
                    "status": 500
                }
            }
            log_api_action(request, "/shell", "run_shell_command", 500, str(resp))
            return resp
        full_command = data.command
        if data.run_as_sudo:
            full_command = f"sudo {full_command}"

        latency = round((time.time() - start) * 1000, 2)
        headers = {"X-Payload-Size": str(payload_size), "X-Latency-ms": str(latency)}
        if data.background:
            proc = subprocess.Popen(
                full_command,
                shell=True,
                executable=os.path.expanduser(data.shell),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = proc.communicate()
            exit_code = proc.returncode
            resp = {
                "stdout": redact_secrets(stdout.strip()),
                "stderr": redact_secrets(stderr.strip()),
                "exit_code": exit_code,
                "pid": proc.pid,
                "status": 200
            }
            log_api_action(request, "/shell", "run_shell_command", 200, str(resp))
            return resp
        else:
            result = subprocess.run(
                full_command,
                shell=True,
                executable=os.path.expanduser(data.shell),
                capture_output=True,
                text=True
            )
            resp = {
                "stdout": redact_secrets(result.stdout.strip()),
                "stderr": redact_secrets(result.stderr.strip()),
                "exit_code": result.returncode,
                "status": 200
            }
            log_api_action(request, "/shell", "run_shell_command", 200, str(resp))
            return resp
    except Exception as e:
        resp = {
            "result": {
                "error": {"code": "subprocess_error", "message": str(e)},
                "status": 500
            }
        }
        log_api_action(request, "/shell", "run_shell_command", 500, str(resp))
        return resp

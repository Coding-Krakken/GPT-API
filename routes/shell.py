from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess
import re
import os
from utils.auth import verify_key

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
def run_shell_command(data: ShellCommand):
    if not data.command or not data.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty or whitespace.")
    try:
        if data.fault == 'permission':
            return {'error': 'Permission denied', 'code': 403}
        if data.fault == 'io':
            return {'error': 'I/O error occurred', 'code': 500}
        full_command = data.command
        if data.run_as_sudo:
            full_command = f"sudo {full_command}"

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
            return {
                "stdout": redact_secrets(stdout.strip()),
                "stderr": redact_secrets(stderr.strip()),
                "exit_code": exit_code,
                "pid": proc.pid
            }
        else:
            result = subprocess.run(
                full_command,
                shell=True,
                executable=os.path.expanduser(data.shell),
                capture_output=True,
                text=True
            )
            return {
                "stdout": redact_secrets(result.stdout.strip()),
                "stderr": redact_secrets(result.stderr.strip()),
                "exit_code": result.returncode
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

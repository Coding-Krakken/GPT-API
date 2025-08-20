from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess
import os
from utils.auth import verify_key

router = APIRouter()

class ShellCommand(BaseModel):
    command: str
    run_as_sudo: bool = False
    background: bool = False
    shell: str = "/bin/bash"  # Default shell for UNIX systems

@router.post("/", dependencies=[Depends(verify_key)])
def run_shell_command(data: ShellCommand):
    try:
        full_command = data.command
        if data.run_as_sudo:
            full_command = f"sudo {full_command}"

        if data.background:
            full_command += " &"

        result = subprocess.run(
            full_command,
            shell=True,
            executable=os.path.expanduser(data.shell),
            capture_output=True,
            text=True
        )

        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

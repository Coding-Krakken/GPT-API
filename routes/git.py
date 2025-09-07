from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os
from utils.auth import verify_key

router = APIRouter()

class GitRequest(BaseModel):
    action: str
    path: str
    args: str = ""

@router.post("/", dependencies=[Depends(verify_key)])
def handle_git_command(req: GitRequest):
    try:
        repo_path = os.path.abspath(os.path.expanduser(req.path))
        if not os.path.isdir(repo_path):
            raise HTTPException(status_code=400, detail="Invalid repository path")

        cmd = f"git -C \"{repo_path}\" {req.action} {req.args}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # If dubious ownership error, add safe.directory and retry once
        if "dubious ownership" in result.stderr:
            safe_cmd = f"git config --global --add safe.directory '{repo_path}'"
            subprocess.run(safe_cmd, shell=True)
            # Retry the original command
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

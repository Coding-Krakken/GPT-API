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
    """
    Handle git operations with user-friendly errors and repo validation.
    """
    try:
        repo_path = os.path.abspath(os.path.expanduser(req.path))
        if not os.path.isdir(repo_path):
            raise HTTPException(status_code=400, detail="Invalid repository path: not a directory.")
        # Check if this is a git repo
        git_dir = os.path.join(repo_path, ".git")
        if not os.path.isdir(git_dir):
            raise HTTPException(status_code=400, detail="Target path is not a git repository. Please initialize with 'git init' or specify a valid repo.")

        def check_git_identity(repo_path):
            def get_config(key):
                try:
                    result = subprocess.run(["git", "-C", repo_path, "config", "--get", key], capture_output=True, text=True)
                    return result.stdout.strip()
                except Exception:
                    return None
            name = get_config("user.name")
            email = get_config("user.email")
            return bool(name and email)

        cmd = f"git -C \"{repo_path}\" {req.action} {req.args}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # If dubious ownership error, add safe.directory and retry once
        if "dubious ownership" in result.stderr:
            safe_cmd = f"git config --global --add safe.directory '{repo_path}'"
            subprocess.run(safe_cmd, shell=True)
            # Retry the original command
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # User-friendly error for common git errors
        if result.returncode != 0:
            if "not a git repository" in result.stderr:
                return {"error": "Target path is not a git repository. Please initialize with 'git init' or specify a valid repo.", "exit_code": result.returncode}
            if "fatal" in result.stderr:
                return {"error": result.stderr.strip().splitlines()[-1], "exit_code": result.returncode}
            return {"error": result.stderr.strip(), "exit_code": result.returncode}
        # Check for identity config on commit/push
        if req.action in ["commit", "push"]:
            if not check_git_identity(repo_path):
                raise HTTPException(status_code=400, detail="Git user.name and user.email must be set for commit/push. Use 'git config user.name' and 'git config user.email' in your repo.")
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

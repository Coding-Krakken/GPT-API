from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os
from typing import List
from utils.auth import verify_key

router = APIRouter()





class GitRequest(BaseModel):
    action: str
    path: str
    args: str = ""
    debug: bool = False

    def validate(self, allowed_actions: List[str]):
        if not self.action or self.action not in allowed_actions:
            raise HTTPException(status_code=400, detail={
                "error": {
                    "code": "invalid_action",
                    "message": f"Action '{self.action}' is not supported. Allowed: {allowed_actions}"
                }
            })
        if not self.path or not isinstance(self.path, str):
            raise HTTPException(status_code=400, detail={
                "error": {
                    "code": "invalid_path",
                    "message": "A valid 'path' string is required."
                }
            })



import time

@router.post("/", dependencies=[Depends(verify_key)])
def handle_git_command(req: GitRequest):
    """
    Handle git operations with user-friendly errors, repo validation, and metadata.
    """

    start = time.time()
    payload_size = None
    allowed_actions = [
        "init", "status", "add", "commit", "push", "pull", "clone", "log", "diff", "checkout", "branch", "merge", "reset", "remote", "fetch", "rebase", "tag", "config"
    ]
    try:
        req.validate(allowed_actions)
        repo_path = os.path.abspath(os.path.expanduser(req.path))
        payload_size = len(str(req.dict()))
        debug_info = [] if req.debug else None
        # If directory does not exist and action is init, create it
        if not os.path.exists(repo_path):
            if req.action == "init":
                os.makedirs(repo_path, exist_ok=True)
                if req.debug:
                    debug_info.append(f"Created directory: {repo_path}")
            else:
                if req.debug:
                    debug_info.append(f"Path does not exist: {repo_path}")
                return {"error": {"code": "invalid_path", "message": f"Repository path '{repo_path}' does not exist."}, "status": 400, "debug": debug_info}
        if not os.path.isdir(repo_path):
            if req.debug:
                debug_info.append(f"Not a directory: {repo_path}")
            return {
                "error": {
                    "code": "not_a_directory",
                    "message": f"Repository path '{repo_path}' is not a directory. To create a new git repository, use 'git init <directory>' or specify a valid repo path."
                },
                "status": 400,
                "debug": debug_info
            }

        git_dir = os.path.join(repo_path, ".git")
        has_git = os.path.isdir(git_dir)
        has_gitignore = os.path.isfile(os.path.join(repo_path, ".gitignore"))

        # Accept directory if it is a git repo, or has .gitignore, or is empty and action is init
        if not has_git:
            if req.action == "init":
                if req.debug:
                    debug_info.append(f"Allowing init on non-git directory: {repo_path}")
                pass  # allow init
            elif has_gitignore:
                if req.debug:
                    debug_info.append(f".gitignore exists in: {repo_path}")
                pass  # allow if .gitignore exists
            else:
                files = os.listdir(repo_path)
                if not files:
                    if req.debug:
                        debug_info.append(f"Empty directory, not a git repo: {repo_path}")
                    return {
                        "error": {
                            "code": "not_a_git_repo",
                            "message": f"Target path '{repo_path}' is empty and not a git repo. Run 'git init' in this directory to initialize a repository. For help, see 'git help init'."
                        },
                        "status": 400,
                        "debug": debug_info
                    }
                else:
                    if req.debug:
                        debug_info.append(f"Not a git repo, contents: {files}")
                    return {
                        "error": {
                            "code": "not_a_git_repo",
                            "message": f"Target path '{repo_path}' is not a git repository. Run 'git init' in this directory to initialize a repository. For help, see 'git help init'."
                        },
                        "contents": files,
                        "status": 400,
                        "debug": debug_info
                    }

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
        if req.debug:
            debug_info.append(f"Running command: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # If dubious ownership error, add safe.directory and retry once
        if "dubious ownership" in result.stderr:
            safe_cmd = f"git config --global --add safe.directory '{repo_path}'"
            if req.debug:
                debug_info.append(f"Dubious ownership detected, running: {safe_cmd}")
            subprocess.run(safe_cmd, shell=True)
            # Retry the original command
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # User-friendly error for common git errors
        if result.returncode != 0:
            latency = round((time.time() - start) * 1000, 2)
            err_msg = result.stderr.strip()
            code = "git_error"
            if "not a git repository" in err_msg:
                code = "not_a_git_repo"
                msg = f"Target path '{repo_path}' is not a git repository. Please initialize with 'git init' or specify a valid repo. For help, see 'git help init'."
            elif "fatal" in err_msg:
                msg = err_msg.splitlines()[-1]
            else:
                msg = err_msg
            err_resp = {
                "error": {
                    "code": code,
                    "message": msg
                },
                "exit_code": result.returncode,
                "latency_ms": latency,
                "payload_size": payload_size,
                "status": 400
            }
            if req.debug:
                err_resp["debug"] = debug_info
            return err_resp
        # Check for identity config on commit/push
        if req.action in ["commit", "push"]:
            if not check_git_identity(repo_path):
                resp = {
                    "error": {
                        "code": "missing_identity",
                        "message": "Git user.name and user.email must be set for commit/push. Use 'git config user.name' and 'git config user.email' in your repo."
                    },
                    "status": 400
                }
                if req.debug:
                    resp["debug"] = debug_info
                return resp
        latency = round((time.time() - start) * 1000, 2)
        resp = {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
            "latency_ms": latency,
            "payload_size": payload_size,
            "status": 200
        }
        if req.debug:
            resp["debug"] = debug_info
        return resp
    except HTTPException as e:
        # If detail is already a dict with error, just return it
        if isinstance(e.detail, dict) and "error" in e.detail:
            if req.debug and isinstance(e.detail, dict):
                e.detail["debug"] = debug_info
            return e.detail
        resp = {"error": {"code": "http_exception", "message": str(e.detail)}, "status": e.status_code}
        if req.debug:
            resp["debug"] = debug_info
        return resp
    except Exception as e:
        resp = {"error": {"code": "internal_error", "message": f"Internal error: {str(e)}"}, "status": 500}
        if req.debug:
            resp["debug"] = debug_info
        return resp

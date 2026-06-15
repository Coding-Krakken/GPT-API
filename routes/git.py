from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import subprocess
import os
import time
import shlex
from utils.auth import verify_key

router = APIRouter()


class GitRequest(BaseModel):
    action: Optional[str] = None
    path: Optional[str] = None
    args: str = ""
    files: Optional[List[str]] = None
    message: Optional[str] = None
    branch: Optional[str] = None
    base: Optional[str] = None
    remote: Optional[str] = None
    patch: Optional[str] = None
    dry_run: bool = False
    include_untracked: bool = False
    max_commits: int = Field(default=20, ge=1, le=1000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    debug: bool = False


ACTIONS = {"init","status","diff","add","commit","branch","checkout","merge","rebase","pull","push","log","show","stash","tag","reset","restore","blame","worktree","clean","apply_patch","create_pr_summary","clone","remote","fetch","config"}


def _run(argv, cwd=None, timeout=300, input_text=None):
    return subprocess.run(argv, cwd=cwd, input=input_text, capture_output=True, text=True, timeout=timeout)


def _repo(path):
    return os.path.abspath(os.path.expanduser(path))


def _changed(repo):
    r = _run(["git", "-C", repo, "status", "--porcelain"], timeout=30)
    return [line[3:] for line in r.stdout.splitlines() if len(line) > 3]


def _identity_ok(repo):
    name = _run(["git", "-C", repo, "config", "--get", "user.name"], timeout=30).stdout.strip()
    email = _run(["git", "-C", repo, "config", "--get", "user.email"], timeout=30).stdout.strip()
    return bool(name and email)


def _cmd_for(req: GitRequest, repo: str):
    qargs = shlex.split(req.args) if req.args else []
    action = req.action
    if action == "status":
        return ["git", "-C", repo, "status", "--short" if req.include_untracked else "--porcelain"] + qargs
    if action == "diff":
        cmd = ["git", "-C", repo, "diff"]
        if req.base:
            cmd.append(req.base)
        if req.files:
            cmd += ["--"] + req.files
        return cmd + qargs
    if action == "add":
        return ["git", "-C", repo, "add"] + (req.files or qargs or ["."])
    if action == "commit":
        return ["git", "-C", repo, "commit", "-m", req.message or "Automated commit"] + qargs
    if action == "branch":
        return ["git", "-C", repo, "branch"] + ([req.branch] if req.branch else []) + qargs
    if action == "checkout":
        return ["git", "-C", repo, "checkout"] + ([req.branch] if req.branch else qargs)
    if action == "merge":
        return ["git", "-C", repo, "merge", req.branch or req.base or ""] + qargs
    if action == "rebase":
        return ["git", "-C", repo, "rebase", req.base or req.branch or ""] + qargs
    if action == "pull":
        return ["git", "-C", repo, "pull"] + ([req.remote] if req.remote else []) + ([req.branch] if req.branch else []) + qargs
    if action == "push":
        return ["git", "-C", repo, "push"] + ([req.remote] if req.remote else []) + ([req.branch] if req.branch else []) + qargs
    if action == "log":
        return ["git", "-C", repo, "log", f"-{req.max_commits}", "--oneline"] + qargs
    if action == "show":
        return ["git", "-C", repo, "show"] + qargs
    if action == "stash":
        return ["git", "-C", repo, "stash"] + qargs
    if action == "tag":
        return ["git", "-C", repo, "tag"] + qargs
    if action == "reset":
        return ["git", "-C", repo, "reset"] + qargs
    if action == "restore":
        return ["git", "-C", repo, "restore"] + (req.files or qargs)
    if action == "blame":
        return ["git", "-C", repo, "blame"] + (req.files or qargs)
    if action == "worktree":
        return ["git", "-C", repo, "worktree"] + qargs
    if action == "clean":
        return ["git", "-C", repo, "clean"] + (qargs or ["-fd"])
    if action == "init":
        return ["git", "-C", repo, "init"] + qargs
    if action in ["remote", "fetch", "config"]:
        return ["git", "-C", repo, action] + qargs
    if action == "clone":
        return ["git", "clone"] + qargs + [repo]
    raise ValueError(f"Unsupported action: {action}")


@router.post("/", dependencies=[Depends(verify_key)])
def handle_git_command(req: GitRequest):
    start = time.time()
    debug = []
    try:
        if not req.action or req.action not in ACTIONS:
            return {"error": {"code": "invalid_action", "message": f"Unsupported git action: {req.action}"}, "status": 400}
        if not req.path:
            return {"error": {"code": "invalid_path", "message": "A valid path string is required."}, "status": 400}
        repo = _repo(req.path)
        if req.action == "init":
            os.makedirs(repo, exist_ok=True)
        elif req.action != "clone" and not os.path.isdir(repo):
            return {"error": {"code": "invalid_path", "message": f"Repository path does not exist: {repo}"}, "status": 400}
        if req.action not in ["init", "clone"]:
            r = _run(["git", "-C", repo, "rev-parse", "--is-inside-work-tree"], timeout=30)
            if r.returncode != 0:
                return {"error": {"code": "not_a_git_repo", "message": r.stderr.strip() or f"Not a git repository: {repo}"}, "status": 400}
        if req.action in ["commit", "push"] and not _identity_ok(repo):
            return {"error": {"code": "missing_identity", "message": "Git user.name and user.email must be set for commit/push."}, "status": 400}
        if req.action == "apply_patch":
            if not req.patch:
                return {"error": {"code": "missing_patch", "message": "patch is required for apply_patch"}, "status": 400}
            cmd = ["git", "-C", repo, "apply", "--check"]
            if req.dry_run:
                r = _run(cmd, timeout=req.timeout_seconds, input_text=req.patch)
            else:
                check = _run(cmd, timeout=req.timeout_seconds, input_text=req.patch)
                if check.returncode != 0:
                    r = check
                else:
                    r = _run(["git", "-C", repo, "apply"], timeout=req.timeout_seconds, input_text=req.patch)
        elif req.action == "create_pr_summary":
            base = req.base or "HEAD~1"
            diff = _run(["git", "-C", repo, "diff", base], timeout=req.timeout_seconds)
            status = _run(["git", "-C", repo, "status", "--short"], timeout=req.timeout_seconds)
            return {"summary": f"Changed files:\n{status.stdout}\n\nDiff against {base}:\n{diff.stdout[:12000]}", "diff": diff.stdout, "changed_files": _changed(repo), "exit_code": 0, "status": 200, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
        else:
            argv = _cmd_for(req, repo)
            argv = [x for x in argv if x != ""]
            if req.dry_run:
                return {"stdout": shlex.join(argv), "stderr": "", "exit_code": 0, "dry_run": True, "status": 200, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
            r = _run(argv, timeout=req.timeout_seconds)
            if "dubious ownership" in r.stderr:
                _run(["git", "config", "--global", "--add", "safe.directory", repo], timeout=30)
                r = _run(argv, timeout=req.timeout_seconds)
        status = 200 if r.returncode == 0 else 400
        resp = {"stdout": r.stdout.strip(), "stderr": r.stderr.strip(), "exit_code": r.returncode, "changed_files": _changed(repo) if os.path.isdir(os.path.join(repo,'.git')) else [], "status": status, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
        if req.action == "diff":
            resp["diff"] = r.stdout
        if req.debug:
            resp["debug"] = debug
        return resp
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import worktrees

router = APIRouter(dependencies=[Depends(verify_key)])


class WorkspaceCreateRequest(BaseModel):
    repo_path: str
    task_id: str
    strategy: str = "git_worktree"
    base_branch: Optional[str] = None


class WorkspacePathRequest(BaseModel):
    workspace_path: str


class WorkspaceDestroyRequest(BaseModel):
    workspace_path: str
    force: bool = False
    keep_branch: bool = True


def _wrap(fn, *args, **kwargs):
    start = time.time()
    try:
        out = fn(*args, **kwargs)
        out.update({"status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)})
        return out
    except PolicyError as exc:
        return {"error": {"code": exc.code, "message": exc.message}, "status": 400}
    except Exception as exc:
        return {"error": {"code": "internal_error", "message": str(exc)}, "status": 500}


@router.post("/create")
def workspace_create(req: WorkspaceCreateRequest):
    if req.strategy != "git_worktree":
        return {"error": {"code": "unsupported_strategy", "message": "Only git_worktree is supported."}, "status": 400}
    return _wrap(worktrees.create_worktree, req.repo_path, req.task_id, req.base_branch)


@router.post("/status")
def workspace_status(req: WorkspacePathRequest):
    return _wrap(worktrees.status, req.workspace_path)


@router.post("/diff")
def workspace_diff(req: WorkspacePathRequest):
    return _wrap(worktrees.diff, req.workspace_path)


@router.post("/destroy")
def workspace_destroy(req: WorkspaceDestroyRequest):
    return _wrap(worktrees.destroy, req.workspace_path, req.force, req.keep_branch)

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import task_ledger

router = APIRouter(dependencies=[Depends(verify_key)])


class TaskCreateRequest(BaseModel):
    task: str
    repo_path: str
    workspace_path: str | None = None
    metadata: dict[str, Any] | None = None

class TaskUpdateRequest(BaseModel):
    task_id: str
    status: str | None = None
    workspace_path: str | None = None
    metadata: dict[str, Any] | None = None

class TaskIdRequest(BaseModel):
    task_id: str

class TaskListRequest(BaseModel):
    status: str | None = None

class TaskOwnerRequest(BaseModel):
    task_id: str
    owner: str = "coding-gpt"

class TaskCancelRequest(BaseModel):
    task_id: str
    reason: str | None = None

class TaskLogRequest(BaseModel):
    task_id: str
    event_type: str
    data: dict[str, Any] | None = None

class TaskArtifactRequest(BaseModel):
    task_id: str
    name: str
    artifact: dict[str, Any]


def _wrap(fn, *args, **kwargs):
    start = time.time()
    try:
        out = fn(*args, **kwargs)
        return {"status": 200, "result": out, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}

@router.post("/create")
def task_create(req: TaskCreateRequest): return _wrap(task_ledger.create, req.task, req.repo_path, req.workspace_path, req.metadata)

@router.post("/update")
def task_update(req: TaskUpdateRequest): return _wrap(task_ledger.update, req.task_id, req.status, req.workspace_path, req.metadata)

@router.post("/read")
def task_read(req: TaskIdRequest): return _wrap(task_ledger.read, req.task_id)

@router.post("/list")
def task_list(req: TaskListRequest): return _wrap(task_ledger.list_tasks, req.status)

@router.post("/cancel")
def task_cancel(req: TaskCancelRequest): return _wrap(task_ledger.cancel, req.task_id, req.reason)

@router.post("/lock")
def task_lock(req: TaskOwnerRequest): return _wrap(task_ledger.lock, req.task_id, req.owner)

@router.post("/claim")
def task_claim(req: TaskOwnerRequest): return _wrap(task_ledger.claim, req.task_id, req.owner)

@router.post("/unlock")
def task_unlock(req: TaskOwnerRequest): return _wrap(task_ledger.unlock, req.task_id, req.owner)

@router.post("/log")
def task_log(req: TaskLogRequest): return _wrap(task_ledger.log_event, req.task_id, req.event_type, req.data)

@router.post("/artifacts")
def task_artifacts(req: TaskArtifactRequest): return _wrap(task_ledger.add_artifact, req.task_id, req.name, req.artifact)

@router.post("/resume")
def task_resume(req: TaskIdRequest): return _wrap(task_ledger.resume, req.task_id)


class TaskGcRequest(BaseModel):
    max_age_ms: int = 604800000
    statuses: list[str] | None = None
    dry_run: bool = True

class TaskLockTtlRequest(BaseModel):
    task_id: str
    owner: str = "coding-gpt"
    ttl_ms: int = 1800000

@router.post("/status-summary")
def task_status_summary(): return _wrap(task_ledger.status_summary)

@router.post("/gc")
def task_gc(req: TaskGcRequest): return _wrap(task_ledger.gc, req.max_age_ms, req.statuses, req.dry_run)

@router.post("/lock-ttl")
def task_lock_ttl(req: TaskLockTtlRequest): return _wrap(task_ledger.lock_ttl, req.task_id, req.owner, req.ttl_ms)

@router.post("/artifact-index")
def task_artifact_index(req: TaskIdRequest): return _wrap(task_ledger.artifact_index, req.task_id)


@router.post("/validate-artifacts")
def task_validate_artifacts(req: TaskIdRequest): return _wrap(task_ledger.validate_required_artifacts, req.task_id)

@router.post("/phase-contract")
def task_phase_contract(req: TaskIdRequest): return _wrap(task_ledger.phase_contract, req.task_id)

@router.post("/iteration-summary")
def task_iteration_summary(req: TaskIdRequest): return _wrap(task_ledger.iteration_summary, req.task_id)

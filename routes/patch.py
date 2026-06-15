from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import patching
from utils import validation_workflow

router = APIRouter(dependencies=[Depends(verify_key)])


class PatchRequest(BaseModel):
    workspace_path: str
    patch: str
    strict: bool = True
    require_preview: bool = True

class PatchRecordedRequest(BaseModel):
    workspace_path: str
    patch: str
    task_id: str | None = None
    label: str | None = None

class PatchHistoryRequest(BaseModel):
    workspace_path: str
    task_id: str | None = None

class PatchRevertRecordedRequest(BaseModel):
    workspace_path: str
    patch_id: str

class PatchRiskRequest(BaseModel):
    workspace_path: str
    patch: str
    max_files: int = 25
    max_lines: int = 2000


def _patch_preflight(workspace_path: str, patch: str | None = None) -> dict:
    preflight = validation_workflow.git_preflight(workspace_path)
    changed = (preflight.get("modifiedFiles") or []) + (preflight.get("untrackedFiles") or [])
    if patch:
        changed.extend(_files_from_patch(patch))
    changed = list(dict.fromkeys(changed))
    return {
        "repoPreflight": preflight,
        "securityReview": validation_workflow.security_review(workspace_path, changed),
        "typeSafety": validation_workflow.type_safety_warnings(workspace_path, changed),
    }


def _files_from_patch(patch: str) -> list[str]:
    out: list[str] = []
    for line in (patch or "").splitlines():
        if line.startswith(("+++ b/", "--- a/")):
            rel = line[6:]
            if rel and rel != "/dev/null":
                out.append(rel)
        elif line.startswith("diff --git a/") and " b/" in line:
            try:
                out.append(line.split(" b/", 1)[1].strip())
            except Exception:
                pass
    return out


def _wrap(fn, *args, workspace_path: str | None = None, patch: str | None = None):
    start = time.time()
    try:
        out = fn(*args)
        if workspace_path:
            out.update(_patch_preflight(workspace_path, patch))
        out.update({"status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)})
        return out
    except PolicyError as exc:
        return {"error": {"code": exc.code, "message": exc.message}, "status": 400}
    except Exception as exc:
        return {"error": {"code": "internal_error", "message": str(exc)}, "status": 500}

@router.post("/preview")
def patch_preview(req: PatchRequest): return _wrap(patching.preview, req.workspace_path, req.patch, workspace_path=req.workspace_path, patch=req.patch)

@router.post("/apply")
def patch_apply(req: PatchRequest): return _wrap(patching.apply_patch, req.workspace_path, req.patch, workspace_path=req.workspace_path, patch=req.patch)

@router.post("/revert")
def patch_revert(req: PatchRequest): return _wrap(patching.revert_patch, req.workspace_path, req.patch, workspace_path=req.workspace_path, patch=req.patch)

@router.post("/apply-recorded")
def patch_apply_recorded(req: PatchRecordedRequest): return _wrap(patching.apply_recorded, req.workspace_path, req.patch, req.task_id, req.label, workspace_path=req.workspace_path, patch=req.patch)

@router.post("/history")
def patch_history(req: PatchHistoryRequest): return _wrap(patching.history, req.workspace_path, req.task_id, workspace_path=req.workspace_path)

@router.post("/revert-recorded")
def patch_revert_recorded(req: PatchRevertRecordedRequest): return _wrap(patching.revert_recorded, req.workspace_path, req.patch_id, workspace_path=req.workspace_path)

@router.post("/validate-risk")
def patch_validate_risk(req: PatchRiskRequest): return _wrap(patching.validate_risk, req.workspace_path, req.patch, req.max_files, req.max_lines, workspace_path=req.workspace_path, patch=req.patch)

from __future__ import annotations

import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import env_tools

router = APIRouter(dependencies=[Depends(verify_key)])

class EnvRequest(BaseModel):
    workspace_path: str

class EnvPrepareApprovedRequest(BaseModel):
    workspace_path: str
    approved: bool = False


def _wrap(fn, *args):
    start = time.time()
    try:
        out = fn(*args)
        out.update({"status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)})
        return out
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}

@router.post("/discover")
def env_discover(req: EnvRequest): return _wrap(env_tools.discover, req.workspace_path)

@router.post("/doctor")
def env_doctor(req: EnvRequest): return _wrap(env_tools.doctor, req.workspace_path)

@router.post("/prepare-dry-run")
def env_prepare_dry_run(req: EnvRequest): return _wrap(env_tools.prepare_plan, req.workspace_path)

@router.post("/prepare-approved")
def env_prepare_approved(req: EnvPrepareApprovedRequest): return _wrap(env_tools.prepare_approved, req.workspace_path, req.approved)

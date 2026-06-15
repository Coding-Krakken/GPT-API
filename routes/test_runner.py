from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import test_discovery

router = APIRouter(dependencies=[Depends(verify_key)])


class WorkspacePathRequest(BaseModel):
    workspace_path: str


class RunTestRequest(BaseModel):
    workspace_path: str
    command_name: str
    timeout_seconds: int = 120
    validationMode: str | None = None
    target_ref: str | None = None


def _wrap(fn, *args):
    start = time.time()
    try:
        out = fn(*args)
        out.update({"status": out.get("status", 200), "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)})
        return out
    except PolicyError as exc:
        return {"error": {"code": exc.code, "message": exc.message}, "status": 400}
    except Exception as exc:
        return {"error": {"code": "internal_error", "message": str(exc)}, "status": 500}


@router.post("/discover")
def test_discover(req: WorkspacePathRequest):
    return _wrap(test_discovery.discover, req.workspace_path)


@router.post("/run")
def test_run(req: RunTestRequest):
    return _wrap(test_discovery.run_discovered, req.workspace_path, req.command_name, req.timeout_seconds, req.validationMode, req.target_ref)

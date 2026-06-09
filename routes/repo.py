from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import repo_intel

router = APIRouter(dependencies=[Depends(verify_key)])


class RepoOverviewRequest(BaseModel):
    repo_path: str
    max_depth: int = 4


class RepoSearchRequest(BaseModel):
    repo_path: str
    query: str
    globs: Optional[list[str]] = None
    max_results: int = 50


class RepoReadContextRequest(BaseModel):
    repo_path: str
    files: list[str]
    max_bytes_per_file: int = 50000


class RepoSymbolsRequest(BaseModel):
    repo_path: str
    files: Optional[list[str]] = None


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


@router.post("/overview")
def repo_overview(req: RepoOverviewRequest):
    return _wrap(repo_intel.overview, req.repo_path, req.max_depth)


@router.post("/search")
def repo_search(req: RepoSearchRequest):
    return _wrap(repo_intel.search, req.repo_path, req.query, req.globs, req.max_results)


@router.post("/read-context")
def repo_read_context(req: RepoReadContextRequest):
    return _wrap(repo_intel.read_context, req.repo_path, req.files, req.max_bytes_per_file)


@router.post("/symbols")
def repo_symbols(req: RepoSymbolsRequest):
    return _wrap(repo_intel.symbols, req.repo_path, req.files)

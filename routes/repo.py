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


class RepoRelevantContextRequest(BaseModel):
    repo_path: str
    task: str
    diagnostics: Optional[list[dict]] = None
    max_files: int = 12


@router.post("/instructions")
def repo_instructions(req: RepoOverviewRequest):
    return _wrap(repo_intel.repo_instructions, req.repo_path)


@router.post("/dependency-graph")
def repo_dependency_graph(req: RepoOverviewRequest):
    return _wrap(repo_intel.dependency_graph, req.repo_path)


@router.post("/test-map")
def repo_test_map(req: RepoOverviewRequest):
    return _wrap(repo_intel.test_map, req.repo_path)


@router.post("/relevant-context")
def repo_relevant_context(req: RepoRelevantContextRequest):
    return _wrap(repo_intel.relevant_context, req.repo_path, req.task, req.diagnostics, req.max_files)


class RepoReferencesRequest(BaseModel):
    repo_path: str
    symbol: str
    max_results: int = 100

class RepoSymbolReferencesRequest(BaseModel):
    repo_path: str
    symbols: list[str]
    max_results_per_symbol: int = 50

class RepoChangedContextRequest(BaseModel):
    repo_path: str
    base_ref: str | None = None

class RepoRecentHistoryRequest(BaseModel):
    repo_path: str
    query: str | None = None
    max_commits: int = 20

@router.post("/callgraph")
def repo_callgraph(req: RepoOverviewRequest): return _wrap(repo_intel.callgraph, req.repo_path)

@router.post("/references")
def repo_references(req: RepoReferencesRequest): return _wrap(repo_intel.references, req.repo_path, req.symbol, req.max_results)

@router.post("/symbol-references")
def repo_symbol_references(req: RepoSymbolReferencesRequest): return _wrap(repo_intel.symbol_references, req.repo_path, req.symbols, req.max_results_per_symbol)

@router.post("/route-map")
def repo_route_map(req: RepoOverviewRequest): return _wrap(repo_intel.route_map, req.repo_path)

@router.post("/changed-context")
def repo_changed_context(req: RepoChangedContextRequest): return _wrap(repo_intel.changed_context, req.repo_path, req.base_ref)

@router.post("/recent-history-context")
def repo_recent_history_context(req: RepoRecentHistoryRequest): return _wrap(repo_intel.recent_history_context, req.repo_path, req.query, req.max_commits)

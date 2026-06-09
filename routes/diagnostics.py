from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils import diagnostics

router = APIRouter(dependencies=[Depends(verify_key)])


class DiagnosticsParseRequest(BaseModel):
    tool: str
    stdout: str = ""
    stderr: str = ""


class DiagnosticsSuggestRequest(BaseModel):
    diagnostics: list[dict[str, Any]]
    max_files: int = 20


@router.post("/parse")
def diagnostics_parse(req: DiagnosticsParseRequest):
    start = time.time()
    out = diagnostics.parse(req.tool, req.stdout, req.stderr)
    out.update({"status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)})
    return out


@router.post("/suggest-context")
def diagnostics_suggest_context(req: DiagnosticsSuggestRequest):
    start = time.time()
    out = diagnostics.suggest_context(req.diagnostics, req.max_files)
    out.update({"status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)})
    return out


class DiagnosticsTriageRequest(BaseModel):
    diagnostics: list[dict[str, Any]]
    task: str | None = None
    max_files: int = 20

@router.post("/triage")
def diagnostics_triage(req: DiagnosticsTriageRequest):
    start = time.time()
    out = diagnostics.triage(req.diagnostics, req.task, req.max_files)
    out.update({"status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)})
    return out

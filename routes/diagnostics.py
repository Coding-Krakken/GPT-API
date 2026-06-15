from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils import diagnostics
from utils.metrics import metrics_registry

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


@router.get("/performance")
def diagnostics_performance(window_seconds: int | None = 900):
    return metrics_registry.snapshot(window_seconds=window_seconds)


@router.get("/ngrok")
def diagnostics_ngrok():
    start = time.time()
    admin_url = "http://127.0.0.1:4040/api/tunnels"
    try:
        with urllib.request.urlopen(admin_url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        tunnels = payload.get("tunnels", [])
        public_urls = [t.get("public_url") for t in tunnels if t.get("public_url")]
        return {
            "status": "ok",
            "admin_alive": True,
            "admin_url": admin_url,
            "tunnel_count": len(tunnels),
            "public_urls": public_urls,
            "tunnels": tunnels,
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000),
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "status": "unavailable",
            "admin_alive": False,
            "admin_url": admin_url,
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "tunnel_count": 0,
            "public_urls": [],
            "tunnels": [],
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000),
        }

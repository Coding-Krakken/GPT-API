from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from utils.auth import verify_key
import psutil
import time
import os
import subprocess
import socket
import json

router = APIRouter()


class MonitorRequest(BaseModel):
    type: str = "cpu"
    live: bool = False
    pid: Optional[int] = None
    job_id: Optional[str] = None
    path: Optional[str] = None
    tail: int = Field(default=100, ge=1, le=10000)
    since: Optional[str] = None
    interval_ms: int = Field(default=1000, ge=100)
    samples: int = Field(default=1, ge=1, le=1000)
    filter: Optional[str] = None


@router.get("/", summary="Monitor health check")
def monitor_health():
    return {"result": "Monitor endpoint is live."}


def _meta(start):
    return {"latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}


def _tail_file(path: str, n: int):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()[-n:]


@router.post("/", summary="Monitor metrics or subscribe to events", dependencies=[Depends(verify_key)])
def monitor_system(req: MonitorRequest):
    start = time.time()
    try:
        t = (req.type or "cpu").lower()
        if req.live:
            return {"result": f"Live {t} monitoring not implemented. Use WebSocket or polling.", **_meta(start)}
        if t == "cpu":
            vals = [psutil.cpu_percent(interval=req.interval_ms / 1000.0) for _ in range(req.samples)]
            return {"metrics": {"cpu_percent": vals[-1], "samples": vals}, "result": str(vals[-1]), **_meta(start)}
        if t == "memory":
            mem = psutil.virtual_memory()
            return {"result": json.dumps({"total_gb": round(mem.total/1e9,2), "used_gb": round(mem.used/1e9,2), "percent": mem.percent}), "metrics": {"total": mem.total, "available": mem.available, "used": mem.used, "free": mem.free, "percent": mem.percent}, **_meta(start)}
        if t == "disk":
            usage = psutil.disk_usage(req.path or "/")
            total_gb=round(usage.total/1e9,2); used_gb=round(usage.used/1e9,2); percent=round((used_gb/total_gb)*100,1) if total_gb else 0
            return {"result": json.dumps({"total_gb": total_gb, "used_gb": used_gb, "percent": percent}), "metrics": {"path": req.path or "/", "total": usage.total, "used": usage.used, "free": usage.free, "percent": percent}, **_meta(start)}
        if t == "network":
            net = psutil.net_io_counters()
            return {"result": json.dumps({"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv}), "metrics": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "packets_sent": net.packets_sent, "packets_recv": net.packets_recv}, **_meta(start)}
        if t == "filesystem":
            rows = []
            for p in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    rows.append({"device": p.device, "mountpoint": p.mountpoint, "fstype": p.fstype, "total": u.total, "used": u.used, "free": u.free, "percent": u.percent})
                except Exception:
                    rows.append({"device": p.device, "mountpoint": p.mountpoint, "error": "unavailable"})
            return {"result": json.dumps({r.get("mountpoint", r.get("device", "unknown")): ({"total_gb": round(r["total"]/1e9,2), "used_gb": round(r["used"]/1e9,2), "percent": r["percent"]} if "total" in r else "unavailable") for r in rows}), "metrics": {"filesystems": rows}, **_meta(start)}
        if t == "performance":
            perf={"cpu_percent": psutil.cpu_percent(interval=0.1), "memory_percent": psutil.virtual_memory().percent, "disk_percent": psutil.disk_usage(req.path or "/").percent}
            return {"result": json.dumps(perf), "metrics": perf, **_meta(start)}
        if t == "process":
            if req.pid:
                p = psutil.Process(req.pid)
                return {"metrics": {"pid": p.pid, "name": p.name(), "status": p.status(), "cpu_percent": p.cpu_percent(interval=0.1), "memory_percent": p.memory_percent(), "cmdline": p.cmdline()}, **_meta(start)}
            procs = []
            for p in psutil.process_iter(["pid", "name", "status", "username", "cmdline"]):
                try:
                    info = p.info
                    if req.filter and req.filter.lower() not in " ".join(map(str, info.values())).lower():
                        continue
                    procs.append(info)
                    if len(procs) >= req.tail:
                        break
                except Exception:
                    pass
            return {"metrics": {"processes": procs}, **_meta(start)}
        if t == "ports":
            conns = []
            for c in psutil.net_connections(kind="inet"):
                if c.laddr:
                    conns.append({"fd": c.fd, "family": str(c.family), "type": str(c.type), "local": f"{c.laddr.ip}:{c.laddr.port}", "remote": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None, "status": c.status, "pid": c.pid})
                    if len(conns) >= req.tail:
                        break
            return {"metrics": {"connections": conns}, **_meta(start)}
        if t == "logs":
            if not req.path:
                return {"result": "Log stream not yet implemented", **_meta(start)}
            lines = _tail_file(os.path.abspath(os.path.expanduser(req.path)), req.tail)
            if req.filter:
                lines = [l for l in lines if req.filter in l]
            return {"result": "\n".join([l.rstrip("\n") for l in lines]), "logs": [l.rstrip("\n") for l in lines], **_meta(start)}
        if t == "git":
            path = os.path.abspath(os.path.expanduser(req.path or os.getcwd()))
            r = subprocess.run(["git", "-C", path, "status", "--short"], capture_output=True, text=True, timeout=30)
            return {"metrics": {"path": path, "clean": not bool(r.stdout.strip()), "status_short": r.stdout.splitlines(), "stderr": r.stderr, "exit_code": r.returncode}, **_meta(start)}
        if t == "tests":
            path = os.path.abspath(os.path.expanduser(req.path or os.getcwd()))
            r = subprocess.run(["pytest", "--collect-only", "-q", path], capture_output=True, text=True, timeout=120)
            return {"metrics": {"path": path, "collected_output": r.stdout, "stderr": r.stderr, "exit_code": r.returncode}, **_meta(start)}
        if t == "docker":
            r = subprocess.run(["docker", "ps", "--format", "{{json .}}"], capture_output=True, text=True, timeout=30)
            return {"metrics": {"containers": [x for x in r.stdout.splitlines() if x], "stderr": r.stderr, "exit_code": r.returncode}, **_meta(start)}
        if t in ["jobs", "custom"]:
            return {"result": ("Custom monitoring not implemented. Please specify details." if t == "custom" else f"{t} monitoring requires caller-specific context; no active registry is attached to /monitor."), **_meta(start)}
        return JSONResponse(status_code=400, content={"error": f"Unknown monitor type: {t}", "status": 400, **_meta(start)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": str(e)}, "status": 500, **_meta(start)})

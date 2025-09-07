
"""
Monitor API endpoint for system metrics and live monitoring.
Supports: cpu, memory, disk, network, logs, filesystem, performance, custom.
All responses are OpenAPI-compliant and user-friendly.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from utils.auth import verify_key
import psutil
import json

router = APIRouter()

class MonitorRequest(BaseModel):
    type: str = "cpu"
    live: bool = False

@router.get("/", summary="Monitor health check")
def monitor_health():
    """Health check for /monitor endpoint."""
    return {"result": "Monitor endpoint is live."}

@router.post("/", summary="Monitor metrics or subscribe to events", dependencies=[Depends(verify_key)])
def monitor_system(req: MonitorRequest):
    """Monitor system metrics or events. Returns JSON with 'result' or 'error'."""
    try:
        t = req.type.lower() if req.type else "cpu"
        if req.live:
            return {"result": f"Live {t} monitoring not implemented. Use WebSocket or polling."}
        if t == "cpu":
            return {"result": str(psutil.cpu_percent(interval=1))}
        elif t == "memory":
            mem = psutil.virtual_memory()
            data = {
                "total_gb": round(mem.total / 1e9, 2),
                "used_gb": round(mem.used / 1e9, 2),
                "percent": mem.percent
            }
            return {"result": json.dumps(data)}
        elif t == "disk":
            usage = psutil.disk_usage("/")
            data = {
                "total_gb": round(usage.total / 1e9, 2),
                "used_gb": round(usage.used / 1e9, 2),
                "percent": usage.percent
            }
            return {"result": json.dumps(data)}
        elif t == "network":
            net = psutil.net_io_counters()
            data = {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv
            }
            return {"result": json.dumps(data)}
        elif t == "logs":
            return {"result": "Log stream not yet implemented"}
        elif t == "filesystem":
            try:
                partitions = psutil.disk_partitions()
                fs_data = {}
                for p in partitions:
                    try:
                        usage = psutil.disk_usage(p.mountpoint)
                        fs_data[p.mountpoint] = {
                            "total_gb": round(usage.total / 1e9, 2),
                            "used_gb": round(usage.used / 1e9, 2),
                            "percent": usage.percent
                        }
                    except Exception:
                        fs_data[p.mountpoint] = "unavailable"
                return {"result": json.dumps(fs_data)}
            except Exception as e:
                return {"error": f"Filesystem info error: {str(e)}"}
        elif t == "performance":
            try:
                perf = {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage("/").percent
                }
                return {"result": json.dumps(perf)}
            except Exception as e:
                return {"error": f"Performance info error: {str(e)}"}
        elif t == "custom":
            return {"result": "Custom monitoring not implemented. Please specify details."}
        else:
            return JSONResponse(status_code=400, content={"error": f"Unknown monitor type: {t}. Supported: cpu, memory, disk, network, logs, filesystem, performance, custom."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Internal error: {str(e)}"})

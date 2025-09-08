
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
import time

router = APIRouter()

class MonitorRequest(BaseModel):
    type: str = "cpu"
    live: bool = False

@router.get("/", summary="Monitor health check")
def monitor_health():
    """Health check for /monitor endpoint."""
    return {"result": "Monitor endpoint is live."}

@router.get("/", summary="Monitor health check")
def monitor_health():
    """Health check for /monitor endpoint."""
    return {"result": "Monitor endpoint is live."}

@router.post("/", summary="Monitor metrics or subscribe to events", dependencies=[Depends(verify_key)])
def monitor_system(req: MonitorRequest):
    """Monitor system metrics or events. Returns JSON with 'result' or 'error'."""
    start_time = time.time()
    try:
        t = req.type.lower() if req.type else "cpu"
        if req.live:
            return {"result": f"Live {t} monitoring not implemented. Use WebSocket or polling."}
        if t == "cpu":
            result = {"result": str(psutil.cpu_percent(interval=1))}
        elif t == "memory":
            mem = psutil.virtual_memory()
            data = {
                "total_gb": round(mem.total / 1e9, 2),
                "used_gb": round(mem.used / 1e9, 2),
                "percent": round(mem.used / mem.total * 100, 1)  # Calculate percent from original values
            }
            result = {"result": json.dumps(data)}
        elif t == "disk":
            usage = psutil.disk_usage("/")
            data = {
                "total_gb": round(usage.total / 1e9, 2),
                "used_gb": round(usage.used / 1e9, 2),
                "percent": round(usage.used / usage.total * 100, 1)  # Calculate percent from original values
            }
            result = {"result": json.dumps(data)}
        elif t == "network":
            net = psutil.net_io_counters()
            data = {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv
            }
            result = {"result": json.dumps(data)}
        elif t == "logs":
            result = {"result": "Log stream not yet implemented"}
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
                            "percent": round(usage.used / usage.total * 100, 1)  # Calculate percent from original values
                        }
                    except Exception:
                        fs_data[p.mountpoint] = "unavailable"
                result = {"result": json.dumps(fs_data)}
            except Exception as e:
                result = {"error": f"Filesystem info error: {str(e)}"}
        elif t == "performance":
            try:
                perf = {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage("/").percent
                }
                result = {"result": json.dumps(perf)}
            except Exception as e:
                result = {"error": f"Performance info error: {str(e)}"}
        elif t == "custom":
            result = {"result": "Custom monitoring not implemented. Please specify details."}
        else:
            result = JSONResponse(status_code=400, content={"error": f"Unknown monitor type: {t}. Supported: cpu, memory, disk, network, logs, filesystem, performance, custom."})
        
        latency_ms = round((time.time() - start_time) * 1000, 2)
        timestamp = int(time.time() * 1000)
        
        if isinstance(result, dict):
            result["latency_ms"] = latency_ms
            result["timestamp"] = timestamp
        # For JSONResponse, we can't modify it easily, so return dict instead
        elif isinstance(result, JSONResponse):
            content = result.body.decode() if hasattr(result, 'body') else str(result)
            try:
                data = json.loads(content)
                data["latency_ms"] = latency_ms
                data["timestamp"] = timestamp
                return JSONResponse(status_code=result.status_code, content=data)
            except:
                return result
        
        return result
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        timestamp = int(time.time() * 1000)
        return JSONResponse(status_code=500, content={"error": f"Internal error: {str(e)}", "latency_ms": latency_ms, "timestamp": timestamp})

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from utils.auth import verify_key
import psutil, datetime

router = APIRouter()

class MonitorRequest(BaseModel):
    type: str = "cpu"
    live: bool = False

@router.post("/", dependencies=[Depends(verify_key)])
def monitor_system(req: MonitorRequest):
    try:
        if req.type == "cpu":
            return {"usage_percent": psutil.cpu_percent(interval=1)}
        elif req.type == "memory":
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / 1e9, 2),
                "used_gb": round(mem.used / 1e9, 2),
                "percent": mem.percent
            }
        elif req.type == "disk":
            usage = psutil.disk_usage("/")
            return {
                "total_gb": round(usage.total / 1e9, 2),
                "used_gb": round(usage.used / 1e9, 2),
                "percent": usage.percent
            }
        elif req.type == "network":
            net = psutil.net_io_counters()
            return {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv
            }
        elif req.type == "logs":
            return {"message": "Log stream not yet implemented"}
        else:
            return {"error": "Unknown monitor type"}
    except Exception as e:
        return {"error": str(e)}

from fastapi import APIRouter, Depends
from utils.auth import verify_key
import platform, socket, psutil, time, os

router = APIRouter()

@router.get("/", dependencies=[Depends(verify_key)])
def get_system_info():
    try:
        return {
            "os": platform.system(),
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
            "architecture": platform.machine(),
            "cpu": platform.processor(),
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "memory_total_gb": round(psutil.virtual_memory().total / 1e9, 2),
            "memory_usage_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage("/").percent,
            "uptime_seconds": time.time() - psutil.boot_time(),
            "current_user": os.getlogin()
        }
    except Exception as e:
        return {"error": str(e)}

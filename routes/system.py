from fastapi import APIRouter, Depends
from utils.auth import verify_key
import platform, socket, psutil, time, os

router = APIRouter()

@router.get("/", dependencies=[Depends(verify_key)])
def get_system_info():
    start_time = time.time()
    try:
        cpu_info = platform.processor()
        if not cpu_info:
            # Fallback to uname info if processor is empty
            cpu_info = platform.uname().processor
        if not cpu_info:
            # Final fallback
            cpu_info = "Unknown"
            
        result = {
            "os": platform.system(),
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
            "architecture": platform.machine(),
            "cpu": cpu_info,
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),  # Use GiB like the test
            "memory_usage_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage("/").percent,
            "uptime_seconds": time.time() - psutil.boot_time(),
            "current_user": os.getlogin()
        }
        latency_ms = round((time.time() - start_time) * 1000, 2)
        result["latency_ms"] = latency_ms
        result["timestamp"] = int(time.time() * 1000)
        return result
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {"error": str(e), "latency_ms": latency_ms, "timestamp": int(time.time() * 1000)}

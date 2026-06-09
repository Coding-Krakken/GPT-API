from fastapi import APIRouter, Depends
from utils.auth import verify_key
import platform, socket, psutil, time, os, getpass

router = APIRouter()

@router.get("/", dependencies=[Depends(verify_key)])
def get_system_info():
    start_time = time.time()
    try:
        cpu_info = platform.processor()
        if not cpu_info:
            cpu_info = platform.uname().processor
        if not cpu_info:
            cpu_info = "Unknown"

        try:
            current_user = getpass.getuser()
        except Exception:
            current_user = os.environ.get("USER", "unknown")

        vm = psutil.virtual_memory()
        du = psutil.disk_usage("/")

        result = {
            "os": platform.system(),
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
            "architecture": platform.machine(),
            "cpu": cpu_info,
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "memory_total_gb": round(vm.total / (1024**3), 2),
            "memory_usage_percent": vm.percent,
            "disk_usage_percent": du.percent,
            "uptime_seconds": time.time() - psutil.boot_time(),
            "current_user": current_user,
        }

        latency_ms = round((time.time() - start_time) * 1000, 2)
        result["latency_ms"] = latency_ms
        result["timestamp"] = int(time.time() * 1000)
        return result

    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "error": repr(e),
            "latency_ms": latency_ms,
            "timestamp": int(time.time() * 1000),
        }

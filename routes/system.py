from fastapi import APIRouter, Depends
from utils.auth import verify_key
import platform
import socket
import psutil
import time
import os
import getpass
import shutil
import subprocess

router = APIRouter()


def _version(cmd):
    exe = shutil.which(cmd)
    if not exe:
        return {"available": False}
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5)
        return {"available": True, "path": exe, "version": (r.stdout or r.stderr).splitlines()[0] if (r.stdout or r.stderr) else ""}
    except Exception as e:
        return {"available": True, "path": exe, "error": str(e)}


@router.get("/", dependencies=[Depends(verify_key)])
def get_system_info():
    start = time.time()
    try:
        vm = psutil.virtual_memory()
        du = psutil.disk_usage("/")
        user = getpass.getuser() if hasattr(getpass, "getuser") else os.environ.get("USER", "unknown")
        tool_names = ["python", "python3", "node", "npm", "pnpm", "yarn", "git", "pytest", "flake8", "black", "mypy", "ruff", "eslint", "prettier", "go", "cargo", "rustc", "javac", "gcc", "g++", "docker", "patch", "rg"]
        tools = {name: bool(shutil.which(name)) for name in tool_names}
        shells = [s for s in ["/bin/bash", "/bin/sh", shutil.which("bash"), shutil.which("sh"), shutil.which("zsh"), shutil.which("fish")] if s]
        package_managers = [m for m in ["pip", "pipx", "poetry", "uv", "npm", "pnpm", "yarn", "apt", "pacman", "brew", "cargo", "go"] if shutil.which(m)]
        result = {
            "os": platform.system(),
            "platform": platform.platform(),
            "arch": platform.machine(),
            "architecture": platform.machine(),
            "hostname": socket.gethostname(),
            "user": user,
            "current_user": user,
            "cwd": os.getcwd(),
            "cpu": platform.processor() or platform.uname().processor or "Unknown",
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "cpu_usage_percent": psutil.cpu_percent(interval=0.1),
            "memory": {"total": vm.total, "available": vm.available, "used": vm.used, "free": vm.free, "percent": vm.percent},
            "memory_total_gb": round(vm.total / (1024**3), 2),
            "memory_usage_percent": vm.percent,
            "disk": {"total": du.total, "used": du.used, "free": du.free, "percent": du.percent},
            "disk_usage_percent": du.percent,
            "uptime_seconds": time.time() - psutil.boot_time(),
            "shells": sorted(set(shells)),
            "python": _version("python") if shutil.which("python") else _version("python3"),
            "node": _version("node"),
            "git": _version("git"),
            "package_managers": package_managers,
            "tools": tools,
            "workspace_root": os.environ.get("WORKSPACE_ROOT") or os.getcwd(),
            "limits": {"max_timeout_seconds": 3600, "max_output_bytes": 10485760},
            "meta": {"ok": True, "status": 200},
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000),
        }
        return result
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}

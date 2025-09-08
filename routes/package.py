from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import subprocess
import time
from utils.auth import verify_key

router = APIRouter()

class PackageRequest(BaseModel):
    manager: str
    action: str
    package: str = ""

@router.post("/", dependencies=[Depends(verify_key)])
async def package_post(request: Request):
    start_time = time.time()
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            data = await request.json()
            manager = data.get("manager")
            action = data.get("action")
            package = data.get("package", "")
        except Exception:
            # If JSON parsing fails, fall back to query params
            params = request.query_params
            manager = params.get("manager")
            action = params.get("action")
            package = params.get("package", "")
    else:
        # Accept query params as fallback
        params = request.query_params
        manager = params.get("manager")
        action = params.get("action")
        package = params.get("package", "")
    
    # Validate required fields
    if not manager:
        raise HTTPException(status_code=400, detail="Unsupported package manager")
    if not action:
        raise HTTPException(status_code=400, detail="Unsupported action")
    
    req = PackageRequest(manager=manager, action=action, package=package)
    return handle_package_action(req, start_time)

def handle_package_action(req: PackageRequest, start_time):
    """
    Handle package manager actions with paging/limit for large outputs (e.g., pacman list).
    """
    try:
        base_cmd = {
            "pip": "pip",
            "npm": "npm",
            "apt": "apt-get",
            "pacman": "pacman",
            "brew": "brew",
            "winget": "winget"
        }.get(req.manager)

        if not base_cmd:
            raise HTTPException(status_code=400, detail="Unsupported package manager")

        args = translate_package_args(req.manager, req.action, req.package)
        if not args:
            raise HTTPException(status_code=400, detail="Unsupported action")

        # Add limit for list actions to avoid huge output
        limit = 100
        if req.manager == "pacman" and req.action == "list":
            # Use head to limit output
            cmd = f"{base_cmd} {args} | head -n {limit}"
        elif req.manager == "apt" and req.action == "list":
            cmd = f"{base_cmd} {args} | head -n {limit}"
        elif req.manager == "npm" and req.action == "list":
            cmd = f"{base_cmd} {args} --depth=0 | head -n {limit}"
        else:
            cmd = f"{base_cmd} {args}"

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # Cap output length for very large responses
        max_len = 8000
        stdout = result.stdout
        if len(stdout) > max_len:
            stdout = stdout[:max_len] + "\n...output truncated. Use filtering or pagination for full list."
        response = {
            "stdout": stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "timestamp": int(time.time() * 1000)
        }
        return response
    except HTTPException:
        # Re-raise HTTP exceptions to preserve their status codes
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def translate_package_args(manager: str, action: str, package: str = "") -> str:
    PACMAN_ACTION_MAP = {
        "install": f"-S {package}",
        "remove": f"-R {package}",
        "update": "-Sy",
        "upgrade": "-Syu",
        "list": "-Q"
    }
    PIP_ACTION_MAP = {
        "install": f"install {package}",
        "remove": f"uninstall -y {package}",
        "update": "install --upgrade pip",
        "upgrade": f"install --upgrade {package}",
        "list": "list"
    }
    NPM_ACTION_MAP = {
        "install": f"install {package}",
        "remove": f"uninstall {package}",
        "update": "update",
        "upgrade": "update",
        "list": "list --depth=0"
    }
    APT_ACTION_MAP = {
        "install": f"install -y {package}",
        "remove": f"remove -y {package}",
        "update": "update",
        "upgrade": "upgrade -y",
        "list": "list --installed"
    }
    BREW_ACTION_MAP = {
        "install": f"install {package}",
        "remove": f"uninstall {package}",
        "update": "update",
        "upgrade": "upgrade",
        "list": "list"
    }
    WINGET_ACTION_MAP = {
        "install": f"install {package}",
        "remove": f"uninstall {package}",
        "update": "upgrade --all",
        "upgrade": "upgrade --all",
        "list": "list"
    }
    maps = {
        "pacman": PACMAN_ACTION_MAP,
        "pip": PIP_ACTION_MAP,
        "npm": NPM_ACTION_MAP,
        "apt": APT_ACTION_MAP,
        "brew": BREW_ACTION_MAP,
        "winget": WINGET_ACTION_MAP
    }
    return maps.get(manager, {}).get(action, "")

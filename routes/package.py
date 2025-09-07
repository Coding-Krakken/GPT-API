from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import subprocess
from utils.auth import verify_key

router = APIRouter()

class PackageRequest(BaseModel):
    manager: str
    action: str
    package: str = ""

@router.post("/", dependencies=[Depends(verify_key)])
async def package_post(request: Request):
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        manager = data.get("manager")
        action = data.get("action")
        package = data.get("package", "")
    else:
        # Accept query params as fallback
        params = request.query_params
        manager = params.get("manager")
        action = params.get("action")
        package = params.get("package", "")
    req = PackageRequest(manager=manager, action=action, package=package)
    return handle_package_action(req)

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

def handle_package_action(req: PackageRequest):
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

        cmd = f"{base_cmd} {args}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

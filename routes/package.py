from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess
from utils.auth import verify_key

router = APIRouter()

class PackageRequest(BaseModel):
    manager: str
    action: str
    package: str = ""

@router.post("/", dependencies=[Depends(verify_key)])
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

        cmd_map = {
            "install": f"{base_cmd} install {req.package}",
            "remove": f"{base_cmd} remove {req.package}",
            "update": f"{base_cmd} update",
            "upgrade": f"{base_cmd} upgrade",
            "list": f"{base_cmd} list"
        }

        cmd = cmd_map.get(req.action)
        if not cmd:
            raise HTTPException(status_code=400, detail="Unsupported action")

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

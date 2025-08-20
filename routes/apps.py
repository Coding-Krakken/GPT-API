from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os, platform
from utils.auth import verify_key

router = APIRouter()

class AppRequest(BaseModel):
    action: str
    app: str
    args: str = ""

@router.post("/", dependencies=[Depends(verify_key)])
def handle_app_action(req: AppRequest):
    try:
        if req.action == "launch":
            cmd = f"{req.app} {req.args}"
            subprocess.Popen(cmd, shell=True)
            return {"status": f"Launched {req.app}"}

        elif req.action == "kill":
            kill_cmd = {
                "Windows": f"taskkill /IM {req.app} /F",
                "Linux": f"pkill -f {req.app}",
                "Darwin": f"pkill -f {req.app}"
            }[platform.system()]
            subprocess.run(kill_cmd, shell=True)
            return {"status": f"Killed {req.app}"}

        elif req.action == "list":
            list_cmd = {
                "Windows": "tasklist",
                "Linux": "ps aux",
                "Darwin": "ps aux"
            }[platform.system()]
            result = subprocess.run(list_cmd, shell=True, capture_output=True, text=True)
            return {"stdout": result.stdout}

        else:
            raise HTTPException(status_code=400, detail="Invalid action")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

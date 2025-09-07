from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os, platform
from utils.auth import verify_key

router = APIRouter()

from typing import Optional

class AppRequest(BaseModel):
    action: str
    app: Optional[str] = None
    args: str = ""
    filter: Optional[str] = None  # For filtering app list
    limit: Optional[int] = 100    # For paging app list

@router.post("/", dependencies=[Depends(verify_key)])
def handle_app_action(req: AppRequest):
    try:
        if req.action == "launch":
            if not req.app:
                raise HTTPException(status_code=422, detail="'app' is required for launch action")
            cmd = f"{req.app} {req.args}"
            subprocess.Popen(cmd, shell=True)
            return {"status": f"Launched {req.app}"}

        elif req.action == "kill":
            if not req.app:
                raise HTTPException(status_code=422, detail="'app' is required for kill action")
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
            output = result.stdout
            # Filtering
            if req.filter:
                output = '\n'.join([line for line in output.splitlines() if req.filter.lower() in line.lower()])
            # Pagination/limit
            limit = req.limit if req.limit and req.limit > 0 else 100
            lines = output.splitlines()
            if len(lines) > limit:
                output = '\n'.join(lines[:limit]) + f"\n...output truncated. Use filter or increase limit for more."
            return {"stdout": output}

        else:
            raise HTTPException(status_code=400, detail="Invalid action")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

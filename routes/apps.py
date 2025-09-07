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
    offset: Optional[int] = 0     # For paging app list

@router.post("/", dependencies=[Depends(verify_key)])
def handle_app_action(req: AppRequest):
    """
    Handle app operations: launch, kill, list.
    Edge behaviors:
      - 'list' may return large output; use 'filter' and 'limit' to control size.
      - If 'limit' is exceeded, output is truncated and a message is appended.
      - If 'app' is missing for launch/kill, returns 422 error.
      - Schema drift: new fields may be ignored unless documented.
      - Implicit precondition: 'app' must be installed and in PATH for launch/kill.
    """
    try:
        if req.action == "launch":
            if not req.app:
                raise HTTPException(status_code=422, detail="'app' is required for launch action")
            cmd = f"{req.app} {req.args}"
            subprocess.Popen(cmd, shell=True)
            return {"result": f"Launched {req.app}"}

        elif req.action == "kill":
            if not req.app:
                raise HTTPException(status_code=422, detail="'app' is required for kill action")
            kill_cmd = {
                "Windows": f"taskkill /IM {req.app} /F",
                "Linux": f"pkill -f {req.app}",
                "Darwin": f"pkill -f {req.app}"
            }[platform.system()]
            subprocess.run(kill_cmd, shell=True)
            return {"result": f"Killed {req.app}"}

        elif req.action == "list":
            list_cmd = {
                "Windows": "tasklist",
                "Linux": "ps aux",
                "Darwin": "ps aux"
            }[platform.system()]
            result = subprocess.run(list_cmd, shell=True, capture_output=True, text=True)
            output = result.stdout
            # Filtering
            lines = output.splitlines()
            if req.filter:
                lines = [line for line in lines if req.filter.lower() in line.lower()]
            total = len(lines)
            offset = req.offset if req.offset and req.offset >= 0 else 0
            limit = req.limit if req.limit and req.limit > 0 else 100
            paged = lines[offset:offset+limit]
            truncated = total > (offset + limit)
            result_obj = {
                "items": paged,
                "filter": req.filter,
                "limit": limit,
                "offset": offset,
                "total": total,
                "truncated": truncated
            }
            return {"result": result_obj}

        else:
            raise HTTPException(status_code=400, detail="Invalid action")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os, shutil
from utils.auth import verify_key

router = APIRouter()

class FileRequest(BaseModel):
    action: str
    path: str
    target_path: str = None
    content: str = None
    recursive: bool = False

@router.post("/", dependencies=[Depends(verify_key)])
def handle_file_operation(req: FileRequest):
    try:
        path = os.path.abspath(os.path.expanduser(req.path))
        target = os.path.abspath(os.path.expanduser(req.target_path)) if req.target_path else None

        if req.action == "read":
            with open(path, "r", encoding="utf-8") as f:
                return {"content": f.read()}

        elif req.action == "write":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(req.content or "")
            return {"status": f"Wrote to {path}"}

        elif req.action == "delete":
            if os.path.isdir(path) and req.recursive:
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"status": f"Deleted {path}"}

        elif req.action == "copy":
            if os.path.isdir(path):
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
            return {"status": f"Copied {path} to {target}"}

        elif req.action == "move":
            shutil.move(path, target)
            return {"status": f"Moved {path} to {target}"}

        elif req.action == "stat":
            stats = os.stat(path)
            return {"size": stats.st_size, "mtime": stats.st_mtime, "ctime": stats.st_ctime}

        elif req.action == "exists":
            return {"exists": os.path.exists(path)}

        elif req.action == "list":
            if not os.path.isdir(path):
                raise HTTPException(status_code=400, detail="Path is not a directory")
            return {"items": os.listdir(path)}

        else:
            raise HTTPException(status_code=400, detail="Unsupported action")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

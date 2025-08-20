from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
from utils.auth import verify_key

router = APIRouter()

class RefactorRequest(BaseModel):
    search: str
    replace: str
    dry_run: bool = False
    files: list[str]

@router.post("/", dependencies=[Depends(verify_key)])
def refactor_code(req: RefactorRequest):
    try:
        results = []
        for file in req.files:
            abs_path = os.path.abspath(os.path.expanduser(file))
            if not os.path.isfile(abs_path):
                continue

            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = content.replace(req.search, req.replace)

            if not req.dry_run:
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            results.append({
                "file": file,
                "changed": content != new_content,
                "preview": new_content[:250]  # preview of change
            })

        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

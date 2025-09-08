from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import os
from utils.auth import verify_key

router = APIRouter()

class RefactorRequest(BaseModel):
    search: str = ""
    replace: str = ""
    dry_run: bool = False
    files: list[str] = []
    fault: str = None  # Optional fault injection

@router.post("/", dependencies=[Depends(verify_key)])
async def refactor_code(request: Request):
    """
    Refactor code by search/replace across files.
    Edge behaviors:
      - Skips files that do not exist (no error).
      - If dry_run is True, no files are written.
      - Returns preview of first 250 chars of new content.
      - Schema drift: new fields in request are ignored.
      - Preconditions: files must be writable, search/replace are required.
    """
    try:
        data = await request.json()
        search = data.get("search", "")
        replace = data.get("replace", "")
        dry_run = data.get("dry_run", False)
        files = data.get("files", [])
        fault = data.get("fault")
        
        # Manual validation
        if not search and "search" in data:
            # Empty search is allowed
            pass
        elif not search:
            raise HTTPException(status_code=500, detail={
                "error": {"code": "internal_error", "message": "Missing search parameter"},
                "status": 500
            })
        
        if "files" not in data:
            raise HTTPException(status_code=500, detail={
                "error": {"code": "internal_error", "message": "Missing files parameter"},
                "status": 500
            })

        if fault == 'io':
            return {
                'error': {
                    'code': 'io_error',
                    'message': 'I/O error occurred'
                },
                'status': 500
            }
        
        results = []
        for file in files:
            abs_path = os.path.abspath(os.path.expanduser(file))
            if not os.path.isfile(abs_path):
                continue

            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = content.replace(search, replace)

            if not dry_run:
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            import difflib
            diff = list(difflib.unified_diff(
                content.splitlines(),
                new_content.splitlines(),
                fromfile=file,
                tofile=file,
                lineterm='',
                n=3
            ))
            preview = '\n'.join(diff[:10])
            results.append({
                "file": file,
                "changed": content != new_content,
                "preview": preview
            })

        if dry_run and not any(r["changed"] for r in results):
            return {"result": "No matches found."}
        return {"result": results}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": {"code": "internal_error", "message": str(e)},
            "status": 500
        })

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os
from utils.auth import verify_key

router = APIRouter()

class CodeAction(BaseModel):
    action: str
    path: str
    language: str = "python"
    args: str = ""

@router.post("/", dependencies=[Depends(verify_key)])
def handle_code_action(req: CodeAction):
    try:
        abs_path = os.path.abspath(os.path.expanduser(req.path))
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="File does not exist")

        if req.action == "run":
            cmd = {
                "python": f"python \"{abs_path}\" {req.args}",
                "bash": f"bash \"{abs_path}\" {req.args}",
                "node": f"node \"{abs_path}\" {req.args}",
            }.get(req.language, f"{req.language} \"{abs_path}\" {req.args}")

        elif req.action == "lint":
            cmd = {
                "python": f"flake8 \"{abs_path}\"",
                "js": f"eslint \"{abs_path}\"",
            }.get(req.language, f"echo 'Linter not configured for {req.language}'")

        elif req.action == "test":
            cmd = {
                "python": f"pytest \"{abs_path}\"",
                "js": f"npm test {abs_path}",
            }.get(req.language, f"echo 'Testing not configured for {req.language}'")

        elif req.action == "format":
            cmd = {
                "python": f"black \"{abs_path}\"",
                "js": f"prettier --write \"{abs_path}\"",
            }.get(req.language, f"echo 'Formatter not configured for {req.language}'")

        elif req.action == "fix":
            cmd = {
                "python": f"autopep8 --in-place \"{abs_path}\"",
                "js": f"eslint \"{abs_path}\" --fix",
            }.get(req.language, f"echo 'Fixer not configured for {req.language}'")

        elif req.action == "explain":
            with open(abs_path, 'r', encoding='utf-8') as f:
                return {"code": f.read(), "explanation": "[GPT should explain this]"}

        else:
            raise HTTPException(status_code=400, detail="Invalid action")

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

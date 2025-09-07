from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os
from utils.auth import verify_key

router = APIRouter()

import tempfile

class CodeAction(BaseModel):
    """
    action: required, one of [run, test, lint, fix, format, explain]
    path: required unless content is provided
    content: optional, if provided will be written to a temp file and executed
    language: optional, default 'python'
    args: optional, string of CLI args
    """
    action: str
    path: str = None
    language: str = "python"
    args: str = ""
    content: str = None

@router.post("/", dependencies=[Depends(verify_key)])
def handle_code_action(req: CodeAction):
    try:
        # If content is provided, write to a temp file and use that path
        if req.content:
            with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=f'.{req.language}') as tmp:
                tmp.write(req.content)
                abs_path = tmp.name
        else:
            if not req.path:
                raise HTTPException(status_code=400, detail="Missing 'path' or 'content'")
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
            if req.language == "python":
                # Check if flake8 is installed
                check_cmd = "flake8 --version"
                check_result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
                if check_result.returncode != 0:
                    # Try to install flake8
                    install_cmd = "pip install flake8"
                    subprocess.run(install_cmd, shell=True)
                # Now run lint
                cmd = f"flake8 \"{abs_path}\""
            elif req.language == "js":
                cmd = f"eslint \"{abs_path}\""
            else:
                cmd = f"echo 'Linter not configured for {req.language}'"

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

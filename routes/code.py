from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import subprocess
import os
import tempfile
import time
import hashlib
import shutil
import ast
import shlex
import threading
from utils.audit import redact_text
from utils.auth import verify_key

router = APIRouter()
_LOCK_GUARD = threading.Lock()
_ACTIVE_PATHS = set()


class CodeAction(BaseModel):
    action: Optional[str] = None
    actions: Optional[List[str]] = None
    path: Optional[str] = None
    content: Optional[str] = None
    language: str
    args: str = ""
    argv: Optional[List[str]] = None
    working_dir: Optional[str] = None
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    env: Optional[Dict[str, str]] = None
    stdin: Optional[str] = None
    files: Optional[List[str]] = None
    test_selector: Optional[str] = None
    coverage: bool = False
    fail_fast: bool = False
    max_output_bytes: int = Field(default=1048576, ge=1024, le=10485760)
    dry_run: bool = False
    fault: Optional[str] = None


def _meta(start):
    return {"latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}


def _truncate(text: str, n: int):
    if text is None:
        return ""
    text = redact_text(text) or ""
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= n:
        return text
    return raw[:n].decode("utf-8", errors="replace") + "\n...output truncated"

def _abs(req: CodeAction):
    if req.working_dir:
        cwd = os.path.abspath(os.path.expanduser(req.working_dir))
    elif req.path:
        cwd = os.path.dirname(os.path.abspath(os.path.expanduser(req.path))) or os.getcwd()
    else:
        cwd = os.getcwd()
    return cwd


def _materialize(req: CodeAction):
    if req.content is not None:
        if len(req.content) > 100_000:
            raise ValueError("invalid_content")
        if req.language == "python":
            ast.parse(req.content)
        suffix = {"python":".py","bash":".sh","node":".js","js":".js","javascript":".js","typescript":".ts","go":".go","rust":".rs","java":".java","c":".c","cpp":".cpp","php":".php","ruby":".rb"}.get(req.language, ".txt")
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=suffix, encoding="utf-8")
        tmp.write(req.content)
        tmp.close()
        return tmp.name, True
    if not req.path:
        raise ValueError("missing_path_or_content")
    path = os.path.abspath(os.path.expanduser(req.path))
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return path, False


def _run(argv, req: CodeAction, cwd: str, input_text=None):
    env = os.environ.copy()
    if req.env:
        env.update(req.env)
    if req.dry_run:
        return {"stdout": shlex.join(argv), "stderr": "", "exit_code": 0, "dry_run": True}
    r = subprocess.run(argv, cwd=cwd, env=env, input=input_text if input_text is not None else req.stdin, capture_output=True, text=True, timeout=req.timeout_seconds)
    return {"stdout": _truncate(r.stdout, req.max_output_bytes), "stderr": _truncate(r.stderr, req.max_output_bytes), "exit_code": r.returncode}


def _tool(name):
    return shutil.which(name)


def _diagnostics_from_lines(text, source="tool"):
    diags = []
    for line in (text or "").splitlines()[:500]:
        diags.append({"severity": "error" if "error" in line.lower() or "failed" in line.lower() else "warning", "source": source, "message": line})
    return diags


def _cmd(req: CodeAction, path: str):
    a, lang = req.action, req.language
    extra = req.argv or (shlex.split(req.args) if req.args else [])
    if a == "run":
        return {"python":["python", path], "bash":["bash", path], "node":["node", path], "js":["node", path], "javascript":["node", path], "ruby":["ruby", path], "php":["php", path], "go":["go", "run", path], "rust":["rustc", path, "-o", os.path.join(tempfile.gettempdir(), "code_run_bin")], "java":["java", path], "c":["sh", "-c", f"gcc {shlex.quote(path)} -o /tmp/code_run_c && /tmp/code_run_c"], "cpp":["sh", "-c", f"g++ {shlex.quote(path)} -o /tmp/code_run_cpp && /tmp/code_run_cpp"]}.get(lang, [lang, path]) + extra
    if a == "test":
        if lang == "python":
            cmd = ["pytest"] + ([path] if os.path.isfile(path) else [path])
            if req.test_selector: cmd += ["-k", req.test_selector]
            if req.fail_fast: cmd.append("-x")
            return cmd + extra
        if lang in ["js","javascript","node","typescript"]: return ["npm", "test"] + extra
        if lang == "go": return ["go", "test", "./..."] + extra
        if lang == "rust": return ["cargo", "test"] + extra
    if a == "coverage":
        if lang == "python": return ["pytest", "--cov", path if os.path.isdir(path) else os.path.dirname(path) or "."] + extra
        if lang in ["js","javascript","node","typescript"]: return ["npm", "test", "--", "--coverage"] + extra
    if a == "lint":
        if lang == "python": return (["ruff", "check", path] if _tool("ruff") else ["flake8", path]) + extra
        if lang in ["js","javascript","typescript","node"]: return ["eslint", path] + extra
    if a == "fix":
        if lang == "python": return (["ruff", "check", "--fix", path] if _tool("ruff") else ["autopep8", "--in-place", path]) + extra
        if lang in ["js","javascript","typescript","node"]: return ["eslint", path, "--fix"] + extra
    if a == "format":
        if lang == "python": return (["black", path] if _tool("black") else ["ruff", "format", path]) + extra
        if lang in ["js","javascript","typescript","node"]: return ["prettier", "--write", path] + extra
        if lang == "go": return ["gofmt", "-w", path] + extra
        if lang == "rust": return ["rustfmt", path] + extra
    if a == "typecheck":
        if lang == "python": return ["mypy", path] + extra
        if lang in ["typescript","js","javascript","node"]: return ["npx", "tsc", "--noEmit"] + extra
        if lang == "go": return ["go", "test", "./...", "-run", "^$"] + extra
    if a in ["build","compile"]:
        if lang in ["js","javascript","typescript","node"]: return ["npm", "run", "build"] + extra
        if lang == "go": return ["go", "build", "./..."] + extra
        if lang == "rust": return ["cargo", "build"] + extra
        if lang == "java": return ["javac", path] + extra
        if lang == "c": return ["gcc", path, "-o", path + ".out"] + extra
        if lang == "cpp": return ["g++", path, "-o", path + ".out"] + extra
        if lang == "python": return ["python", "-m", "py_compile", path] + extra
    if a == "install":
        if lang == "python": return ["pip", "install", "-r", "requirements.txt"] + extra
        if lang in ["js","javascript","typescript","node"]: return ["npm", "install"] + extra
        if lang == "go": return ["go", "mod", "download"] + extra
        if lang == "rust": return ["cargo", "fetch"] + extra
    if a == "debug": return _cmd(req.model_copy(update={"action":"run"}), path)
    if a == "profile" and lang == "python": return ["python", "-m", "cProfile", path] + extra
    if a == "benchmark": return _cmd(req.model_copy(update={"action":"run"}), path)
    if a == "trace" and lang == "python": return ["python", "-m", "trace", "--trace", path] + extra
    if a == "dependency_audit":
        if lang == "python": return ["pip-audit"] + extra if _tool("pip-audit") else ["pip", "check"] + extra
        if lang in ["js","javascript","typescript","node"]: return ["npm", "audit"] + extra
        if lang == "rust": return ["cargo", "audit"] + extra
        if lang == "go": return ["govulncheck", "./..."] + extra
    return None


def _static_analyze(path, req):
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    diags = []
    if req.language == "python":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(getattr(node, "func", None), "id", "") in ["eval", "exec"]:
                    diags.append({"file": path, "line": node.lineno, "severity": "warning", "source": "static_analyze", "message": "Use of eval/exec detected"})
        except Exception as e:
            diags.append({"file": path, "severity": "error", "source": "static_analyze", "message": str(e)})
    return {"stdout": f"Static analysis completed: {len(diags)} issue(s)", "stderr": "", "exit_code": 0, "diagnostics": diags}


def _security_scan(path):
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    patterns = ["password=", "secret", "api_key", "eval(", "exec(", "subprocess", "shell=True"]
    diags = []
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        for p in patterns:
            if p.lower() in low:
                diags.append({"file": path, "line": i, "severity": "warning", "source": "security_scan", "message": f"Pattern detected: {p}"})
    return {"stdout": f"Security scan completed: {len(diags)} finding(s)", "stderr": "", "exit_code": 0, "diagnostics": diags}


def _explain_review(path, action):
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    lines = text.splitlines()
    if action == "summarize":
        return {"summary": f"{path}: {len(lines)} lines, {len(text)} chars."}
    if action == "review":
        return {"review": "Automated review completed. Check diagnostics for concrete tool findings.", "suggested_fixes": []}
    if action == "generate_tests":
        name = os.path.splitext(os.path.basename(path))[0]
        return {"artifacts": [{"type": "test_suggestion", "path": f"test_{name}.py", "content": f"def test_{name}_placeholder():\n    assert True\n", "description": "Starter pytest placeholder."}]}
    return {"code": text, "explanation": f"File has {len(lines)} lines. Use summarize/review for structured assistance."}


@router.post("", dependencies=[Depends(verify_key)])
@router.post("/", dependencies=[Depends(verify_key)])
def handle_code_action(req: CodeAction):
    start = time.time()
    if req.actions:
        results = []
        for action in req.actions:
            sub = req.model_copy(update={"action": action, "actions": None})
            res = handle_code_action(sub)
            results.append({"action": action, "result": res})
            inner = res.get("result", res) if isinstance(res, dict) else {}
            if isinstance(inner, dict) and inner.get("exit_code", 0) not in [0, None]:
                break
        return {"chained": True, "results": results, **_meta(start)}
    locked = False
    path = None
    try:
        supported_actions = ["run","test","lint","fix","format","explain","typecheck","build","install","compile","debug","profile","coverage","benchmark","static_analyze","security_scan","dependency_audit","generate_tests","review","summarize","trace","repl"]
        if not req.action or req.action not in supported_actions:
            return {"result": {"error": {"code": "invalid_action", "message": f"action must be one of {supported_actions}"}, "status": 400}, **_meta(start)}
        supported_languages = ["python","js","javascript","bash","node","typescript","go","rust","java","c","cpp"]
        if req.language not in supported_languages:
            return {"result": {"error": {"code": "unsupported_language", "message": f"language must be one of {supported_languages}"}, "status": 400}, **_meta(start)}
        if req.fault == "syntax":
            return {"result": {"error": {"code": "syntax_error", "message": "Syntax error in code"}, "status": 400}, **_meta(start)}
        if req.fault == "io":
            return {"result": {"error": {"code": "io_error", "message": "I/O error occurred"}, "status": 500}, **_meta(start)}
        if req.fault == "permission":
            return {"result": {"error": {"code": "permission_denied", "message": "Permission denied"}, "status": 403}, **_meta(start)}
        if req.path and len(req.path) > 255:
            return {"result": {"error": {"code": "path_too_long", "message": "File path is too long."}, "status": 400}, **_meta(start)}
        if req.path and any(x in req.path for x in ["..", "~", "//", "\\", "|", ";", "`", "$", ">", "<"]):
            return {"result": {"error": {"code": "invalid_path", "message": "Path contains unsafe characters or sequences."}, "status": 400}, **_meta(start)}
        if req.args:
            unsafe = any(x in req.args for x in [";", "|", "`", "$", ">", "<", "&", "&&", "||"])
            try:
                tokens = shlex.split(req.args)
            except Exception:
                tokens, unsafe = [], True
            allowed = {"python": ["--verbose", "-v", "--maxfail", "--disable-warnings"], "js": ["--verbose", "--fix"], "javascript": ["--verbose", "--fix"], "node": [], "bash": []}
            bad_flag = any(t.startswith("-") and t not in allowed.get(req.language, []) for t in tokens)
            if unsafe or bad_flag:
                return {"result": {"error": {"code": "invalid_args", "message": "Unsupported, malformed, or unsafe arguments."}, "status": 400}, **_meta(start)}
        if req.content is not None and req.action == "explain":
            return {"result": {"error": {"code": "unsupported_content", "message": "content is not supported for action 'explain'. Use path."}, "status": 400}, **_meta(start)}
        if req.path:
            expected = {"python": ".py", "js": ".js", "javascript": ".js", "node": ".js", "bash": ".sh", "typescript": ".ts", "go": ".go", "rust": ".rs", "java": ".java", "c": ".c", "cpp": ".cpp", "php": ".php", "ruby": ".rb"}.get(req.language)
            actual = os.path.splitext(req.path)[1].lower()
            if expected and actual != expected:
                return {"result": {"error": {"code": "language_mismatch", "message": f"File extension '{actual}' does not match language '{req.language}' (expected '{expected}')"}, "status": 400}, **_meta(start)}
        path, temp = _materialize(req)
        if not temp:
            with _LOCK_GUARD:
                if path in _ACTIVE_PATHS:
                    return {"result": {"error": {"code": "concurrent_access", "message": "File is currently being processed by another operation."}, "status": 429}, **_meta(start)}
                _ACTIVE_PATHS.add(path)
                locked = True
            time.sleep(0.05)
        cwd = _abs(req)
        if req.action in ["explain","summarize","review","generate_tests"]:
            out = _explain_review(path, req.action)
            if locked:
                with _LOCK_GUARD:
                    _ACTIVE_PATHS.discard(path)
            return {"result": {"action": req.action, "language": req.language, "path": path, **out}, **{k:v for k,v in out.items() if k in ["artifacts","suggested_fixes"]}, **_meta(start)}
        if req.action == "static_analyze":
            out = _static_analyze(path, req)
        elif req.action == "security_scan":
            out = _security_scan(path)
        elif req.action == "repl":
            out = _run(["python" if req.language == "python" else req.language], req, cwd, input_text=req.content or req.stdin or "")
        else:
            argv = _cmd(req, path)
            if not argv:
                return {"result": {"error": {"code": "unsupported_action", "message": f"Unsupported action/language: {req.action}/{req.language}"}, "status": 400}, **_meta(start)}
            if not shutil.which(argv[0]) and argv[0] != "sh":
                return {"result": {"error": {"code": "tool_not_found", "message": f"Executable not found: {argv[0]}"}, "status": 400}, **_meta(start)}
            out = _run(argv, req, cwd)
        diagnostics = out.get("diagnostics") or _diagnostics_from_lines(out.get("stderr", ""), req.action)
        status = 200 if out.get("exit_code", 0) == 0 else 400
        result = {"action": req.action, "language": req.language, "path": path, "stdout": out.get("stdout", ""), "stderr": out.get("stderr", ""), "exit_code": out.get("exit_code", 0), "duration": round((time.time()-start), 4)}
        if req.action == "test" and req.language == "python" and result["exit_code"] == 5:
            result["error"] = {"code": "no_tests_found", "message": "No tests were found in the specified file."}
        elif result["exit_code"] not in [0, None]:
            result["error"] = {"code": "execution_error", "message": f"Process exited with code {result['exit_code']}. See stderr for details."}
        if req.content is not None:
            result["content_hash"] = hashlib.sha256(req.content.encode()).hexdigest()
        if temp:
            try: os.unlink(path)
            except Exception: pass
        if locked:
            with _LOCK_GUARD:
                _ACTIVE_PATHS.discard(path)
        return {"result": result, "diagnostics": diagnostics, "status": status, **_meta(start)}
    except SyntaxError as e:
        if locked and path:
            with _LOCK_GUARD:
                _ACTIVE_PATHS.discard(path)
        return {"result": {"error": {"code": "invalid_content", "message": str(e)}, "status": 400}, **_meta(start)}
    except ValueError as e:
        if locked and path:
            with _LOCK_GUARD:
                _ACTIVE_PATHS.discard(path)
        code = str(e) or "invalid_content"
        return {"result": {"error": {"code": code, "message": code}, "status": 400}, **_meta(start)}
    except FileNotFoundError as e:
        if locked and path:
            with _LOCK_GUARD:
                _ACTIVE_PATHS.discard(path)
        return {"result": {"error": {"code": "file_not_found", "message": str(e)}, "status": 404}, **_meta(start)}
    except subprocess.TimeoutExpired as e:
        if locked and path:
            with _LOCK_GUARD:
                _ACTIVE_PATHS.discard(path)
        return {"result": {"error": {"code": "timeout", "message": str(e), "hint": "Use a shorter command, increase timeout_seconds deliberately, or use /shell action=start for long-running work."}, "status": 408}, **_meta(start)}
    except Exception as e:
        return {"result": {"error": {"code": "internal_error", "message": str(e)}, "status": 500}, **_meta(start)}

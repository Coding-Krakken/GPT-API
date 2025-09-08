from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os, tempfile
import time
from utils.auth import verify_key

router = APIRouter()

class CodeAction(BaseModel):
    """
    action: required unless actions is provided, one of [run, test, lint, fix, format, explain]
    path: required unless content is provided
    content: optional, if provided will be written to a temp file and executed
    language: required, must be one of ['python', 'js', 'bash', 'node']
    args: optional, string of CLI args (validated per language/action)
    actions: optional, list of actions for chaining
    Note: If language is omitted, request will be rejected.
    """
    action: Optional[str] = None
    path: Optional[str] = None
    language: str
    args: str = ""
    fault: Optional[str] = None  # Optional fault injection
    content: Optional[str] = None
    actions: Optional[List[str]] = None  # Optional list for chaining

    def validate_args(self):
        # Only allow known safe args for each action/language, and block all suspicious patterns
        import shlex
        allowed_args = {
            "python": ["--verbose", "-v", "--maxfail", "--disable-warnings"],
            "js": ["--verbose", "--fix"],
            "bash": [],
            "node": [],
        }
        if self.args:
            try:
                tokens = shlex.split(self.args)
            except Exception:
                return False, "malformed_args"
            for arg in tokens:
                # Block any shell metacharacters or suspicious patterns
                if any(x in arg for x in [';', '|', '`', '$', '>', '<', '\\', '&', '&&', '||', '(', ')', '{', '}', '[', ']', '\'"', "'"]):
                    return False, arg
                # Only allow explicitly whitelisted args
                if arg.startswith("-") and arg not in allowed_args.get(self.language, []):
                    return False, arg
                # Disallow any arg that looks like a command or path
                if arg.startswith(('.', '/')):
                    return False, arg
        return True, None

    def validate_content(self):
        # Basic validation for content mode: size, type, and (for Python) syntax
        if self.content is None:
            return True, None
        if not isinstance(self.content, str):
            return False, "content_not_string"
        if len(self.content) > 100_000:
            return False, "content_too_large"
        if self.language == "python":
            try:
                import ast
                ast.parse(self.content)
            except Exception:
                return False, "invalid_python_syntax"
        # Could add more language-specific checks here
        return True, None

    def validate_language(self):
        # Enforce file extension matches language (skip for content mode)
        if self.path:
            ext = os.path.splitext(self.path)[1].lower()
        else:
            # Skip extension validation for content mode
            return True, None, None
        lang_exts = {
            "python": ".py",
            "js": ".js",
            "javascript": ".js",
            "bash": ".sh",
            "node": ".js",
        }
        expected_ext = lang_exts.get(self.language, None)
        if expected_ext and ext != expected_ext:
            return False, expected_ext, ext
        return True, expected_ext, ext

@router.post("/", dependencies=[Depends(verify_key)])
def handle_code_action(req: CodeAction):
    start_time = time.time()
    # Initialize context for storing metadata
    context = {
        "action": req.action,
        "language": req.language,
        "path": req.path if hasattr(req, 'path') else None,
        "duration": 0
    }
    # Chaining support: allow 'actions' as a list for basic chaining (e.g., ["lint", "fix", "run"])
    if req.actions and isinstance(req.actions, list) and req.actions:
        results = []
        # For each action in the chain, create a new request object
        for chained_action in req.actions:
            # Create a new request with the chained action
            chained_req = CodeAction(
                action=chained_action,
                path=req.path,
                language=req.language,
                args=req.args,
                fault=req.fault,
                content=req.content,
                actions=None  # Clear actions to avoid recursion
            )
            result = handle_code_action(chained_req)
            results.append({"action": chained_action, "result": result})
            # If any error, stop chaining and return immediately
            if isinstance(result, dict) and "error" in result.get("result", {}):
                break
        return {"chained": True, "results": results, "latency_ms": round((time.time() - start_time) * 1000, 2), "timestamp": int(time.time() * 1000)}

    """
    Execute, test, lint, and manipulate code files in a safe, validated, and concurrent-aware manner.

    - **Required Fields:**
        - `action`: One of [run, test, lint, fix, format, explain].
        - `language`: Required. Must be one of ['python', 'js', 'bash', 'node'].
        - `path`: Required unless `content` is provided (see below).
    - **In-Memory (content) Support:**
        - Only supported for actions: run, test, lint, fix, format.
        - Not supported for explain (must provide a file path).
        - If `content` is provided for an unsupported action, returns `unsupported_content` error.
        - Content is validated for type, size, and (for Python) syntax before execution.
    - **Supported Languages:**
        - `run`: python, bash, node
        - `lint`, `fix`, `format`, `test`: python, js
    - **Input Validation:**
        - Unsafe file paths, overlong file names, missing/unsupported languages, malformed input, and invalid content are rejected with clear error codes.
        - Only safe, whitelisted CLI arguments are allowed per language/action.
    - **Error Handling:**
        - All errors are returned as structured JSON with `error.code` and `error.message` (e.g., `unsupported_language`, `file_not_found`, `invalid_args`, `invalid_content`, `concurrent_access`, `execution_error`).
        - Subprocess and file handling failures are returned as structured errors with details in `stderr`.
    - **Concurrency:**
        - File actions are protected by a lock; concurrent requests to the same file will return a `concurrent_access` error.
    - **Test Feedback:**
        - If no tests are found, returns `no_tests_found` with a hint on how to add tests.
    - **Runtime Feedback:**
        - All responses include operation duration in seconds.
    """
    # Strict language whitelist
    supported_languages = ["python", "js", "bash", "node"]
    if not req.language or req.language not in supported_languages:
        return {
            "result": {
                "error": {"code": "unsupported_language", "message": f"'language' must be one of {supported_languages}."},
                "status": 400
            },
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "timestamp": int(time.time() * 1000)
        }
    
    # Strict action whitelist
    supported_actions = ["run", "test", "lint", "fix", "format", "explain"]
    if not req.action or req.action not in supported_actions:
        return {
            "result": {
                "error": {"code": "invalid_action", "message": f"'action' must be one of {supported_actions}."},
                "status": 400
            },
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "timestamp": int(time.time() * 1000)
        }
    
    import fcntl
    
    # Initialize lock variables
    lock_acquired = False
    lock_fd = None
    lockfile = None
    
    try:
        # Input validation: path injection, overlong file names
        if req.path:
            if any(x in req.path for x in ['..', '~', '//', '\\', '|', ';', '`', '$', '>', '<']):
                return {
                    "result": {
                        "error": {"code": "invalid_path", "message": "Path contains unsafe characters or sequences."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }
            if len(req.path) > 255:
                return {
                    "result": {
                        "error": {"code": "path_too_long", "message": "File path is too long."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }

        # Argument validation
        valid_args, bad_arg = req.validate_args()
        if not valid_args:
            return {
                "result": {
                    "error": {"code": "invalid_args", "message": f"Unsupported, malformed, or unsafe argument: {bad_arg}"},
                    "status": 400
                },
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }

        # Content validation (if present)
        valid_content, content_err = req.validate_content()
        if not valid_content:
            return {
                "result": {
                    "error": {"code": "invalid_content", "message": f"Invalid content: {content_err}"},
                    "status": 400
                },
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }

        # Language-type matching
        valid_lang, expected_ext, actual_ext = req.validate_language()
        if not valid_lang:
            return {
                "result": {
                    "error": {"code": "language_mismatch", "message": f"File extension '{actual_ext}' does not match language '{req.language}' (expected '{expected_ext}')"},
                    "status": 400
                },
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        if req.fault == 'syntax':
            return {
                "result": {
                    'error': {
                        'code': 'syntax_error',
                        'message': 'Syntax error in code'
                    },
                    'status': 400
                },
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        if req.fault == 'io':
            return {
                "result": {
                    'error': {
                        'code': 'io_error',
                        'message': 'I/O error occurred'
                    },
                    'status': 500
                },
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        if req.fault == 'permission':
            return {
                "result": {
                    'error': {
                        'code': 'permission_denied',
                        'message': 'Permission denied'
                    },
                    'status': 403
                },
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        # If content is provided, write to a temp file and use that path
        supported_content_actions = ["run", "test", "lint", "fix", "format"]
        if req.content:
            if req.action not in supported_content_actions:
                return {
                    "result": {
                        "error": {"code": "unsupported_content", "message": f"'content' is not supported for action '{req.action}'. Please use a file path."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }
            try:
                with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=f'.{req.language}') as tmp:
                    tmp.write(req.content)
                    abs_path = tmp.name
            except Exception as e:
                return {
                    "result": {
                        "error": {"code": "tempfile_error", "message": f"Failed to create temp file: {str(e)}"},
                        "status": 500
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }
        else:
            if not req.path:
                return {
                    "result": {
                        "error": {"code": "missing_path_or_content", "message": "Missing 'path' or 'content'. Please provide a valid file path (e.g., 'script.py') or code content."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }
            abs_path = os.path.abspath(os.path.expanduser(req.path))
            if not os.path.exists(abs_path):
                return {
                    "result": {
                        "error": {"code": "file_not_found", "message": f"File '{req.path}' not found. Use the /files endpoint to create or upload."},
                        "status": 404
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }

        # Concurrency: file lock for all file-based actions
        try:
            lockfile = abs_path + ".lock"
            lock_fd = open(lockfile, "w")
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_acquired = True
        except Exception:
            return {
                "result": {
                    "error": {"code": "concurrent_access", "message": "File is currently being processed by another operation. Try again later."},
                    "status": 429
                },
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }

        if req.action == "run":
            # Only allow supported languages for run
            if req.language not in ["python", "bash", "node"]:
                return {
                    "result": {
                        "error": {"code": "unsupported_language", "message": f"Run not supported for language '{req.language}'. Supported: python, bash, node."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }
            cmd = {
                "python": f"python \"{abs_path}\" {req.args}",
                "bash": f"bash \"{abs_path}\" {req.args}",
                "node": f"node \"{abs_path}\" {req.args}",
            }[req.language]

        elif req.action == "lint":
            if req.language == "python":
                check_cmd = "flake8 --version"
                check_result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
                if check_result.returncode != 0:
                    install_cmd = "pip install flake8"
                    subprocess.run(install_cmd, shell=True)
                cmd = f"flake8 \"{abs_path}\""
            elif req.language == "js":
                cmd = f"eslint \"{abs_path}\""
            else:
                return {
                    "result": {
                        "error": {"code": "unsupported_language", "message": f"Linter not configured for language '{req.language}'. Supported: python, js."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }

        elif req.action == "test":
            if req.language == "python":
                cmd = f"pytest \"{abs_path}\""
            elif req.language == "js":
                cmd = f"npm test {abs_path}"
            else:
                return {
                    "result": {
                        "error": {"code": "unsupported_language", "message": f"Testing not configured for language '{req.language}'. Supported: python, js."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }

        elif req.action == "format":
            if req.language == "python":
                cmd = f"black \"{abs_path}\""
            elif req.language == "js":
                cmd = f"prettier --write \"{abs_path}\""
            else:
                return {
                    "result": {
                        "error": {"code": "unsupported_language", "message": f"Formatter not configured for language '{req.language}'. Supported: python, js."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }

        elif req.action == "fix":
            if req.language == "python":
                cmd = f"autopep8 --in-place \"{abs_path}\""
            elif req.language == "js":
                cmd = f"eslint \"{abs_path}\" --fix"
            else:
                return {
                    "result": {
                        "error": {"code": "unsupported_language", "message": f"Fixer not configured for language '{req.language}'. Supported: python, js."},
                        "status": 400
                    },
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }

        elif req.action == "explain":
            with open(abs_path, 'r', encoding='utf-8') as f:
                return {
                    "result": {"code": f.read(), "explanation": "[GPT should explain this]"},
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": int(time.time() * 1000)
                }

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        except Exception as e:
            duration = time.time() - start_time
            return {
                "result": {
                    "error": {"code": "subprocess_error", "message": f"Failed to execute command: {str(e)}"},
                    "status": 500,
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": -1,
                    "duration": duration
                },
                "latency_ms": round(duration * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        if req.action == "test" and req.language == "python" and result.returncode == 5:
            duration = time.time() - start_time
            return {
                "result": {
                    "error": {
                        "code": "no_tests_found",
                        "message": "No tests were found in the specified file. To add tests, define functions starting with 'test_' or use unittest.TestCase classes."
                    },
                    "status": 200,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "duration": duration
                },
                "latency_ms": round(duration * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        if req.action == "test" and req.language == "python" and result.returncode == 127:
            duration = time.time() - start_time
            return {
                "result": {
                    "error": {
                        "code": "no_tests_found",
                        "message": "No tests were found in the specified file. To add tests, define functions starting with 'test_' or use unittest.TestCase classes."
                    },
                    "status": 200,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "duration": duration
                },
                "latency_ms": round(duration * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        if req.action == "run" and result.returncode == 127:
            duration = time.time() - start_time
            return {
                "result": {
                    "error": {
                        "code": "unsupported_language",
                        "message": f"Interpreter or runtime for language '{req.language}' not found or not supported."
                    },
                    "status": 400,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "duration": duration
                },
                "latency_ms": round(duration * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        if result.returncode != 0 and req.action == "run":
            duration = time.time() - start_time
            return {
                "result": {
                    "error": {
                        "code": "execution_error",
                        "message": f"Process exited with code {result.returncode}. See stderr for details."
                    },
                    "status": 400,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "duration": duration
                },
                "latency_ms": round(duration * 1000, 2),
                "timestamp": int(time.time() * 1000)
            }
        # Special handling for lint: parse output to classify warnings/errors
        if req.action == "lint":
            issues = []
            output = result.stderr + result.stdout
            if req.language == "python" and output:
                for line in output.strip().split('\n'):
                    if ':' in line:
                        parts = line.split(':', 4)
                        if len(parts) >= 4:
                            filename, line_num, col, code, message = parts
                            severity = "error" if code.startswith('E') or code.startswith('F') else "warning"
                            issues.append({
                                "file": filename,
                                "line": int(line_num),
                                "column": int(col),
                                "code": code,
                                "message": message.strip(),
                                "severity": severity
                            })
            elif req.language == "js" and output:
                # Basic parsing for eslint text output
                for line in output.strip().split('\n'):
                    if line.strip():
                        # Simple parsing - could be improved
                        if 'error' in line.lower():
                            severity = "error"
                        elif 'warning' in line.lower():
                            severity = "warning"
                        else:
                            severity = "info"
                        issues.append({
                            "message": line.strip(),
                            "severity": severity
                        })
            context["issues"] = issues
            context["issues_count"] = len(issues)
            context["errors_count"] = len([i for i in issues if i.get("severity") == "error"])
            context["warnings_count"] = len([i for i in issues if i.get("severity") == "warning"])
        # Add context: file path, action, language, and content hash (if content provided)
        import hashlib
        duration = time.time() - start_time
        context["duration"] = duration
        if req.content:
            context["content_hash"] = hashlib.sha256(req.content.encode()).hexdigest()
        result_dict = {
            "result": {
                **context,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        }
        # Add observability fields
        result_dict["latency_ms"] = round(duration * 1000, 2)
        result_dict["timestamp"] = int(time.time() * 1000)
        return result_dict
    finally:
        if lock_acquired and lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
                os.remove(lockfile)
            except Exception:
                pass

    # All error handling is now inside the main try/except/finally block above.

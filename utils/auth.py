# utils/auth.py
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, Request

_here = Path(__file__).resolve().parent
for _candidate in [
    _here.parent / ".env",
    Path("/work/.env"),
    Path("/home/obsidian/GPT-API/.env"),
    Path("/workspace/.env"),
    Path(".env"),
]:
    if _candidate.exists():
        load_dotenv(_candidate, override=False)
        break
else:
    load_dotenv(override=False)


def _configured_keys() -> dict[str, str]:
    legacy = os.getenv("API_KEY", "").strip()
    return {
        "operator": os.getenv("OPERATOR_GPT_API_KEY", legacy).strip(),
        "coding": os.getenv("CODING_GPT_API_KEY", "").strip(),
        "cos": os.getenv("COS_GPT_API_KEY", "").strip(),
        "legacy": legacy,
    }


def _request_key(request: Request) -> str:
    key = request.headers.get("x-api-key", "").strip()
    if key:
        return key
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return auth


def _roles_for_path(path: str) -> set[str]:
    coding_prefixes = (
        "/repo", "/workspace", "/patch", "/test", "/quality",
        "/policy", "/agent/coding-task", "/tasks", "/github", "/diagnostics", "/env", "/coding", "/evals",
    )
    operator_prefixes = (
        "/shell", "/files", "/manageFiles", "/code", "/system", "/monitor",
        "/git", "/package", "/apps", "/refactor", "/batch", "/gpts",
    )
    if path.startswith("/dispatch"):
        return {"operator", "cos"}
    if path.startswith(coding_prefixes):
        return {"coding", "operator"}
    if path.startswith(operator_prefixes):
        return {"operator"}
    return {"operator"}


def verify_key(request: Request):
    keys = _configured_keys()
    supplied = _request_key(request)
    if not supplied:
        raise HTTPException(status_code=403, detail="Missing API key")

    allowed_roles = _roles_for_path(request.url.path)
    for role in allowed_roles:
        configured = keys.get(role, "")
        if configured and supplied == configured:
            return True

    if "operator" in allowed_roles and keys.get("legacy") and supplied == keys["legacy"]:
        return True

    raise HTTPException(status_code=403, detail="Invalid API key for route")


def require_roles(*roles: str):
    def _dep(request: Request):
        supplied = _request_key(request)
        if not supplied:
            raise HTTPException(status_code=403, detail="Missing API key")
        keys = _configured_keys()
        for role in roles:
            configured = keys.get(role, "")
            if configured and supplied == configured:
                return True
        if "operator" in roles and keys.get("legacy") and supplied == keys["legacy"]:
            return True
        raise HTTPException(status_code=403, detail="Invalid API key for role")
    return _dep

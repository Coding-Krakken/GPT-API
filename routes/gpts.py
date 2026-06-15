"""Route: /gpts — Manages custom GPT lifecycle via browser automation (Playwright)."""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from utils.auth import verify_key
from utils.audit import log_api_action

router = APIRouter()

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class DuplicateGPTRequest(BaseModel):
    action: str = "duplicate_and_configure"

    # Source GPT editor URL (required)
    source_editor_url: str = "https://chatgpt.com/gpts/editor/g-6808e46f824481918e21feb6be82a4ab"

    # Fields to override in the duplicated GPT
    name: str
    description: str
    instructions: str

    # Action entry to configure (the domain / label shown in the Actions section)
    action_name: str = "unscrutinized-immotile-jermaine.ngrok-free.dev"

    # Auth for the action — if omitted falls back to ACTION_API_KEY env var
    action_api_key: str | None = None
    action_api_auth_type: str = "bearer"  # "basic" | "bearer" | "custom"

    # Browser / session config (optional — fall back to env vars when omitted)
    user_data_dir: str | None = None      # Chromium profile directory
    session_token: str | None = None      # __Secure-next-auth.session-token[.0]
    session_token_1: str | None = None    # __Secure-next-auth.session-token.1

    headless: bool = True
    create: bool = True                   # Actually click Create; False = leave as draft
    max_wait_seconds: int = 180


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("", dependencies=[Depends(verify_key)])
@router.post("/", dependencies=[Depends(verify_key)], include_in_schema=False)
async def manage_gpts(data: DuplicateGPTRequest, request: Request) -> dict[str, Any]:
    start = time.time()

    if data.action != "duplicate_and_configure":
        resp = {
            "result": {
                "error": {
                    "code": "unsupported_action",
                    "message": f"Unknown action '{data.action}'. Supported: duplicate_and_configure",
                },
                "status": 400,
            },
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000),
        }
        log_api_action(request, "/gpts", data.action, 400, str(resp))
        return resp

    # Resolve API key from request body → env var
    action_api_key = data.action_api_key or os.getenv("ACTION_API_KEY") or os.getenv("API_KEY")
    if not action_api_key:
        raise HTTPException(
            status_code=400,
            detail="action_api_key is required (or set ACTION_API_KEY / API_KEY env var).",
        )

    # Resolve session tokens from request body → env vars
    session_token = data.session_token or os.getenv("CHATGPT_SESSION_TOKEN")
    session_token_1 = data.session_token_1 or os.getenv("CHATGPT_SESSION_TOKEN_1") or None

    # User data dir: request body → env var → file-based profile next to .env
    user_data_dir = (
        data.user_data_dir
        or os.getenv("CHATGPT_PROFILE_DIR")
        or None
    )

    try:
        # Import here so the rest of the API stays operable even if playwright
        # is not installed (the endpoint will simply error at call time).
        from ChatGPT.functions.custom_gpt_creator import duplicate_and_configure_custom_gpt

        result = await duplicate_and_configure_custom_gpt(
            source_editor_url=data.source_editor_url,
            name=data.name,
            description=data.description,
            instructions=data.instructions,
            action_name=data.action_name,
            action_api_key=action_api_key,
            action_api_auth_type=data.action_api_auth_type,
            user_data_dir=user_data_dir,
            session_token=session_token,
            session_token_1=session_token_1,
            headless=data.headless,
            max_wait_seconds=data.max_wait_seconds,
            create=data.create,
        )

        status_code = 200 if result.get("ok") else 500
        resp = {
            "result": result,
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000),
        }
        log_api_action(request, "/gpts", data.action, status_code, str(resp))
        return resp

    except Exception as exc:
        resp = {
            "result": {
                "error": {"code": "automation_error", "message": str(exc)},
                "status": 500,
            },
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000),
        }
        log_api_action(request, "/gpts", data.action, 500, str(resp))
        return resp

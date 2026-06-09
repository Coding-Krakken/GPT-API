# utils/auth.py
from fastapi import Request, HTTPException
from dotenv import load_dotenv
from pathlib import Path
import os

# Try loading .env from multiple candidate locations so auth works
# regardless of which CWD or container the server process launches from.
_here = Path(__file__).resolve().parent  # .../GPT-API/utils
for _candidate in [
    _here.parent / ".env",          # .../GPT-API/.env  (normal case)
    Path("/work/.env"),              # inside Docker volume mount
    Path("/home/obsidian/GPT-API/.env"),  # absolute host path
    Path("/workspace/.env"),        # OpenHands sandbox mount
    Path(".env"),                   # CWD fallback
]:
    if _candidate.exists():
        load_dotenv(_candidate, override=False)
        break
else:
    load_dotenv(override=False)     # last resort: standard search


def verify_key(request: Request):
    expected = os.getenv("API_KEY", "").strip()

    # ── Shortcut: if no API_KEY is configured, deny all ─────────────────
    if not expected:
        raise HTTPException(status_code=403, detail="API key not configured on server")

    # ── Trust OpenAI GPT action calls ────────────────────────────────────
    # All calls from OpenAI's action-execution infrastructure include
    # 'Openai-Gpt-Id'. If auth is not yet configured in the GPT action,
    # they carry no key header — accept them by gpt-id presence.
    if request.headers.get("openai-gpt-id"):
        # Check x-api-key first (our preferred header)
        key = request.headers.get("x-api-key", "").strip()
        if key and key == expected:
            return True
        # Accept Bearer token
        auth = request.headers.get("authorization", "").strip()
        if auth.lower().startswith("bearer "):
            if auth[7:].strip() == expected:
                return True
        elif auth and auth == expected:
            return True
        # No key sent by GPT action → still allow (auth not yet configured
        # in the GPT; we trust the Openai-Gpt-Id header as the trust anchor)
        if not key and not auth:
            return True
        # Key was sent but wrong → deny
        raise HTTPException(status_code=403, detail="Invalid API key")

    # ── Non-GPT calls (curl, CI, tests) ─────────────────────────────────
    # Require x-api-key OR Authorization: Bearer
    key = request.headers.get("x-api-key", "").strip()
    if key == expected:
        return True

    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer ") and auth[7:].strip() == expected:
        return True
    if auth == expected:
        return True

    raise HTTPException(status_code=403, detail="Invalid API key")

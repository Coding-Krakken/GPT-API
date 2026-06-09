# utils/audit.py
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from fastapi import Request

_SECRET_PATTERNS = [
    re.compile(r"(API_KEY\s*=\s*)\S+"),
    re.compile(r"(OPENAI_API_KEY\s*=\s*)\S+"),
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),
]


def _hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _redact(text: str | None) -> str | None:
    if not text:
        return None
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(r"\1[REDACTED]", out)
    return out[:500]


def log_api_action(request: Request, endpoint: str, action: str, status: int, result: str = None):
    try:
        audit_log_path = os.getenv("AUDIT_LOG_PATH", "audit.log")
        auth = request.headers.get("authorization")
        x_key = request.headers.get("x-api-key")
        presented = x_key or auth
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "action": action,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "api_key_present": bool(presented),
            "api_key_hash": _hash(presented),
            "status": status,
            "result": _redact(result),
        }
        with open(audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass

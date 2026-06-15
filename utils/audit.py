# utils/audit.py
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

_DEFAULT_AUDIT_RESULT_BYTES = 8192

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(api[_-]?key|openai[_-]?api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*(['\"]?)[^'\"\s,;}]+"), r"\1=<redacted>"),
    (re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer\s+)?[A-Za-z0-9._~+/=-]{12,}"), r"\1<redacted>"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "<redacted-github-token>"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "<redacted-openai-key>"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"), "<redacted-slack-token>"),
    (re.compile(r"(?i)(database_url|postgres(?:ql)?://)[^'\"\s,;}]+"), "<redacted-database-url>"),
    (re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}"), "<redacted-bcrypt-hash>"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "<redacted-private-key>"),
    (re.compile(r"(?i)(cookie\s*[:=]\s*)[^\n;]+(?:;[^\n;]+)*"), r"\1<redacted>"),
]


def _hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def redact_text(text: Any) -> str | None:
    """Redact sensitive values from text before returning or logging it."""
    if text is None:
        return None
    out = text if isinstance(text, str) else str(text)
    for pattern, replacement in _SECRET_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def redact_and_cap(text: Any, max_bytes: int | None = None) -> tuple[str | None, dict[str, Any]]:
    """Return redacted text plus byte/truncation metadata."""
    if text is None:
        return None, {"result_bytes": 0, "result_truncated": False, "result_redacted": False}
    raw_text = text if isinstance(text, str) else str(text)
    original_bytes = len(raw_text.encode("utf-8", errors="replace"))
    redacted = redact_text(raw_text) or ""
    redacted_changed = redacted != raw_text
    limit = max_bytes or int(os.getenv("AUDIT_RESULT_MAX_BYTES", str(_DEFAULT_AUDIT_RESULT_BYTES)))
    raw = redacted.encode("utf-8", errors="replace")
    truncated = len(raw) > limit
    if truncated:
        redacted = raw[:limit].decode("utf-8", errors="replace") + "\n...audit result truncated"
    return redacted, {
        "result_bytes": original_bytes,
        "result_truncated": truncated,
        "result_redacted": redacted_changed,
    }


def log_api_action(request: Request, endpoint: str, action: str, status: int, result: str = None):
    try:
        audit_log_path = os.getenv("AUDIT_LOG_PATH", "audit.log")
        auth = request.headers.get("authorization")
        x_key = request.headers.get("x-api-key")
        presented = x_key or auth
        safe_result, result_meta = redact_and_cap(result)
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "action": action,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "api_key_present": bool(presented),
            "api_key_hash": _hash(presented),
            "status": status,
            "result": safe_result,
            **result_meta,
        }
        with open(audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

_SECRET_KEY_PARTS = (
    "api_key", "apikey", "x-api-key", "authorization", "token", "secret",
    "password", "credential", "private_key", "session", "cookie",
)
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|credential)\s*[:=]\s*[^\s,;]+"),
]
_MAX_STRING = 2000
_MAX_LIST = 100
_MAX_DICT = 200
_COMMIT_CACHE: str | None = None


def eval_root() -> Path:
    root = Path(os.getenv("EVAL_TELEMETRY_ROOT", "/tmp/gpt-api-evals")).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    return root


def events_path() -> Path:
    return Path(os.getenv("EVAL_TELEMETRY_EVENTS", str(eval_root() / "events.jsonl"))).expanduser().resolve()


def _backend_commit() -> str | None:
    global _COMMIT_CACHE
    if _COMMIT_CACHE is not None:
        return _COMMIT_CACHE
    try:
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=3)
        _COMMIT_CACHE = result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        _COMMIT_CACHE = None
    return _COMMIT_CACHE


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _is_secret_key(key: Any) -> bool:
    lower = str(key).lower()
    return any(part in lower for part in _SECRET_KEY_PARTS)


def sanitize(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    if depth > 8:
        return "<max_depth>"
    if _is_secret_key(key or ""):
        if value in (None, ""):
            return ""
        return {"redacted": True, "sha256_16": _hash_value(str(value))}
    if isinstance(value, str):
        text = value
        for pattern in _SECRET_PATTERNS:
            text = pattern.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=<redacted>", text)
        if len(text) > _MAX_STRING:
            return {"truncated": True, "length": len(text), "preview": text[:_MAX_STRING]}
        return text
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for idx, (k, v) in enumerate(value.items()):
            if idx >= _MAX_DICT:
                out["<truncated_keys>"] = len(value) - _MAX_DICT
                break
            out[str(k)] = sanitize(v, key=str(k), depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [sanitize(v, depth=depth + 1) for v in seq[:_MAX_LIST]]
        if len(seq) > _MAX_LIST:
            out.append({"truncated_items": len(seq) - _MAX_LIST})
        return out
    return str(value)[:_MAX_STRING]


def payload_keys(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        return sorted(str(k) for k in payload.keys())
    return []


def log_event(event_type: str, **fields: Any) -> dict[str, Any]:
    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "timestamp": int(time.time() * 1000),
        "backend_commit": _backend_commit(),
        "schema_version": os.getenv("CODING_GPT_SCHEMA_VERSION", "coding-gpt-core-openapi.yaml"),
    }
    event.update(sanitize(fields))
    path = events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return event


def log_error(event_type: str, exc: BaseException, **fields: Any) -> dict[str, Any]:
    code = getattr(exc, "code", type(exc).__name__)
    message = getattr(exc, "message", str(exc))
    return log_event(event_type, error={"code": code, "message": message}, **fields)

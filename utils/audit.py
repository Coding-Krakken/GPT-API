# utils/audit.py
import os
import json
from datetime import datetime
from fastapi import Request


def log_api_action(request: Request, endpoint: str, action: str, status: int, result: str = None):
    try:
        AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "audit.log")
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "endpoint": endpoint,
            "action": action,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "api_key": request.headers.get("x-api-key", "<none>"),
            "status": status,
            "result": result[:500] if result else None  # Truncate to avoid log bloat
        }
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        # Fail silently to avoid breaking API
        pass

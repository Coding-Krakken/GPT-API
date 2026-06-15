from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    yaml = None

POLICY_LOG_PATH = os.getenv("POLICY_DECISION_LOG_PATH", "logs/policy-decisions.log")
_CONFIRMATION_STRINGS = {"approved", "confirm", "confirmed", "i understand", "yes-i-understand"}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    code: str
    message: str
    risk: str = "low"
    required_confirmation: bool = False
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "code": self.code,
            "message": self.message,
            "risk": self.risk,
            "required_confirmation": self.required_confirmation,
            "reasons": list(self.reasons),
        }


def load_policy_config() -> dict[str, Any]:
    path = Path(os.getenv("GPT_API_POLICY_CONFIG", "config/policy.yaml"))
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def confirmation_present(value: Any = None, *, explicit_confirm: bool | None = None) -> bool:
    if explicit_confirm is True:
        return True
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in _CONFIRMATION_STRINGS:
        return True
    return False


def block_if_confirmation_required(
    *,
    area: str,
    operation: str,
    reasons: Iterable[str],
    confirmed: bool,
    risk: str = "high",
) -> PolicyDecision:
    reason_list = tuple(dict.fromkeys([r for r in reasons if r]))
    if not reason_list:
        return PolicyDecision(True, "allowed", "No policy blockers detected.", risk="low")
    if confirmed:
        decision = PolicyDecision(True, "approved_dangerous_operation", "Dangerous operation allowed by explicit confirmation.", risk=risk, required_confirmation=True, reasons=reason_list)
    else:
        decision = PolicyDecision(False, "confirmation_required", f"{area} operation '{operation}' requires explicit confirmation.", risk=risk, required_confirmation=True, reasons=reason_list)
    log_policy_decision(area=area, operation=operation, decision=decision)
    return decision


def error_payload(decision: PolicyDecision, *, status: int = 403) -> dict[str, Any]:
    return {"error": {"code": decision.code, "message": decision.message, "risk": decision.risk, "reasons": list(decision.reasons), "required_confirmation": decision.required_confirmation}, "policy_decision": decision.as_dict(), "status": status}


def log_policy_decision(*, area: str, operation: str, decision: PolicyDecision, extra: dict[str, Any] | None = None) -> None:
    try:
        path = Path(POLICY_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": int(time.time() * 1000), "area": area, "operation": operation, "decision": decision.as_dict()}
        if extra:
            record["extra"] = extra
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


_DESTRUCTIVE_SHELL_PATTERNS = [
    ("filesystem_delete", re.compile(r"(^|[;&|\s])rm\s+(-[^\n;|&]*[rf][^\n;|&]*|-[^\n;|&]*[fr][^\n;|&]*)(\s|$)", re.I)),
    ("filesystem_format", re.compile(r"\b(mkfs(?:\.[a-z0-9]+)?|wipefs|fdisk|parted|dd)\b", re.I)),
    ("process_kill", re.compile(r"\b(kill\s+-?9?|pkill|killall)\b", re.I)),
    ("service_restart", re.compile(r"\b(systemctl|service)\s+(restart|stop|disable|mask)\b", re.I)),
    ("permission_change", re.compile(r"\bchmod\s+(-R\s+)?777\b|\bchown\s+(-R\s+)?", re.I)),
    ("power_control", re.compile(r"\b(shutdown|reboot|poweroff|halt)\b", re.I)),
]


def shell_danger_reasons(command: str, *, run_as_sudo: bool = False, background: bool = False) -> list[str]:
    reasons: list[str] = []
    if run_as_sudo or re.search(r"(^|[;&|\s])sudo(\s|$)", command or ""):
        reasons.append("sudo/elevated execution requested")
    if background:
        reasons.append("background process launch requested")
    for label, pattern in _DESTRUCTIVE_SHELL_PATTERNS:
        if pattern.search(command or ""):
            reasons.append(f"dangerous shell pattern detected: {label}")
    return reasons


def file_danger_reasons(action: str, *, recursive: bool = False, overwrite_target_exists: bool = False) -> list[str]:
    action = (action or "").lower()
    reasons: list[str] = []
    if action == "delete":
        reasons.append("file or directory deletion requested")
        if recursive:
            reasons.append("recursive deletion requested")
    if action == "move" and overwrite_target_exists:
        reasons.append("move would overwrite an existing target")
    if action == "restore" and overwrite_target_exists:
        reasons.append("restore would overwrite an existing target")
    return reasons


def package_danger_reasons(manager: str, action: str, *, global_install: bool = False) -> list[str]:
    manager = (manager or "").lower()
    action = (action or "").lower()
    reasons: list[str] = []
    if action in {"install", "remove", "update", "upgrade", "sync"}:
        reasons.append(f"package {action} modifies the environment")
    if global_install:
        reasons.append("global package modification requested")
    if manager in {"apt", "pacman", "brew", "winget"} and action in {"install", "remove", "update", "upgrade", "sync"}:
        reasons.append(f"system package manager '{manager}' modification requested")
    return reasons


def git_danger_reasons(action: str) -> list[str]:
    action = (action or "").lower()
    mapping = {
        "push": "network write via git push requested",
        "clean": "git clean may delete untracked files",
        "reset": "git reset may discard local changes",
        "checkout": "git checkout may overwrite files or switch branches",
        "rebase": "git rebase rewrites history/worktree state",
        "merge": "git merge changes worktree/history",
        "stash": "git stash changes worktree state",
    }
    return [mapping[action]] if action in mapping else []


def code_danger_reasons(action: str) -> list[str]:
    action = (action or "").lower()
    if action in {"install", "fix", "format"}:
        return [f"code action '{action}' may modify dependencies or files"]
    return []


def app_danger_reasons(action: str) -> list[str]:
    action = (action or "").lower()
    if action == "launch":
        return ["application/background process launch requested"]
    if action == "kill":
        return ["application/process termination requested"]
    return []


def refactor_danger_reasons(*, apply: bool, dry_run: bool, preview: bool) -> list[str]:
    if apply and not dry_run and not preview:
        return ["refactor apply modifies files"]
    return []

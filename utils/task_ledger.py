from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from utils.policy import PolicyError, ensure_under_allowed_root, worktree_root
from utils import eval_telemetry


LEDGER_DIRNAME = ".gpt-api-tasks"


def _ledger_root() -> Path:
    root = Path(os.getenv("TASK_LEDGER_ROOT", str(worktree_root() / LEDGER_DIRNAME))).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _task_path(task_id: str) -> Path:
    safe = "".join(ch for ch in task_id if ch.isalnum() or ch in "._-")
    if not safe:
        raise PolicyError("invalid_task_id", "Task id is invalid.")
    path = _ledger_root() / f"{safe}.json"
    ensure_under_allowed_root(path)
    return path


def _now() -> int:
    return int(time.time() * 1000)


def create(task: str, repo_path: str, workspace_path: str | None = None, metadata: dict[str, Any] | None = None) -> dict:
    if not task or not task.strip():
        raise PolicyError("invalid_task", "Task text is required.")
    task_id = f"task_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    record = {
        "task_id": task_id,
        "task": task.strip(),
        "repo_path": repo_path,
        "workspace_path": workspace_path,
        "status": "created",
        "metadata": metadata or {},
        "events": [],
        "artifacts": {},
        "created_at": _now(),
        "updated_at": _now(),
    }
    _task_path(task_id).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    eval_telemetry.log_event("task_started", task_id=task_id, repo_path=repo_path, workspace_path=workspace_path, metadata_keys=eval_telemetry.payload_keys(metadata or {}))
    return record


def read(task_id: str) -> dict:
    path = _task_path(task_id)
    if not path.exists():
        raise PolicyError("task_not_found", f"Task not found: {task_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def update(task_id: str, status: str | None = None, workspace_path: str | None = None, metadata: dict[str, Any] | None = None) -> dict:
    record = read(task_id)
    if status:
        record["status"] = status
    if workspace_path:
        record["workspace_path"] = workspace_path
    if metadata:
        record.setdefault("metadata", {}).update(metadata)
    record["updated_at"] = _now()
    _task_path(task_id).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    eval_telemetry.log_event("task_updated", task_id=task_id, status=record.get("status"), workspace_path=record.get("workspace_path"), metadata_keys=eval_telemetry.payload_keys(metadata or {}))
    return record


def log_event(task_id: str, event_type: str, data: dict[str, Any] | None = None) -> dict:
    if not event_type or not event_type.strip():
        raise PolicyError("invalid_event_type", "Event type is required.")
    record = read(task_id)
    record.setdefault("events", []).append({"type": event_type.strip(), "data": data or {}, "timestamp": _now()})
    record["updated_at"] = _now()
    _task_path(task_id).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    eval_telemetry.log_event("task_ledger_event", task_id=task_id, ledger_event_type=event_type.strip(), data_keys=eval_telemetry.payload_keys(data or {}))
    return record



def _redact_artifact(value):
    import re
    if isinstance(value, str):
        text = re.sub(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+", r"\1=<redacted>", value)
        text = re.sub(r"sk-[A-Za-z0-9_-]{20,}", "sk-<redacted>", text)
        return text[:200000]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(term in str(k).lower() for term in ["api_key", "apikey", "token", "secret", "password", "credential"]):
                out[k] = "<redacted>"
            else:
                out[k] = _redact_artifact(v)
        return out
    if isinstance(value, list):
        return [_redact_artifact(v) for v in value[:500]]
    return value


def _artifact_size(value) -> int:
    try:
        return len(json.dumps(value))
    except Exception:
        return 0


def add_artifact(task_id: str, name: str, artifact: dict[str, Any]) -> dict:
    if not name or not name.strip():
        raise PolicyError("invalid_artifact_name", "Artifact name is required.")
    record = read(task_id)
    cleaned = _redact_artifact(artifact)
    max_bytes = int(os.getenv("TASK_ARTIFACT_MAX_BYTES", "250000"))
    size = _artifact_size(cleaned)
    if size > max_bytes:
        cleaned = {"truncated": True, "original_size_bytes": size, "preview": json.dumps(cleaned)[:max_bytes]}
    record.setdefault("artifacts", {})[name.strip()] = {"data": cleaned, "timestamp": _now(), "approx_size_bytes": _artifact_size(cleaned)}
    record["updated_at"] = _now()
    _task_path(task_id).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    eval_telemetry.log_event("artifact_recorded", task_id=task_id, artifact_name=name.strip(), approx_size_bytes=_artifact_size(cleaned), artifact_keys=eval_telemetry.payload_keys(cleaned if isinstance(cleaned, dict) else {}))
    return record


def resume(task_id: str) -> dict:
    record = read(task_id)
    guidance = []
    if record.get("workspace_path"):
        guidance.append("Call /workspace/status and /workspace/diff to inspect current task state.")
    else:
        guidance.append("Call /workspace/create before applying patches.")
    guidance.extend([
        "Use /repo/search and /repo/read-context for focused context.",
        "Use /patch/preview and /patch/apply for edits.",
        "Use /test/discover, /test/run, and /quality/check before completion.",
    ])
    return {"task": record, "resume_guidance": guidance}


def list_tasks(status: str | None = None) -> dict:
    items = []
    for path in sorted(_ledger_root().glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and record.get("status") != status:
            continue
        items.append({"task_id": record.get("task_id"), "task": record.get("task"), "status": record.get("status"), "repo_path": record.get("repo_path"), "workspace_path": record.get("workspace_path"), "updated_at": record.get("updated_at")})
    return {"tasks": items, "count": len(items)}


def cancel(task_id: str, reason: str | None = None) -> dict:
    record = update(task_id, status="cancelled", metadata={"cancel_reason": reason or "cancelled"})
    return log_event(task_id, "cancelled", {"reason": reason or "cancelled", "status": record.get("status")})


def lock(task_id: str, owner: str = "coding-gpt") -> dict:
    record = read(task_id)
    if record.get("locked_by") and record.get("locked_by") != owner:
        raise PolicyError("task_locked", f"Task is already locked by {record.get('locked_by')}")
    record["locked_by"] = owner
    record["updated_at"] = _now()
    _task_path(task_id).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def claim(task_id: str, owner: str = "coding-gpt") -> dict:
    record = lock(task_id, owner)
    record["status"] = "claimed"
    record["updated_at"] = _now()
    _task_path(task_id).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def unlock(task_id: str, owner: str = "coding-gpt") -> dict:
    record = read(task_id)
    if record.get("locked_by") and record.get("locked_by") != owner:
        raise PolicyError("task_locked", f"Task is locked by {record.get('locked_by')}")
    record.pop("locked_by", None)
    record["updated_at"] = _now()
    _task_path(task_id).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def final_report(task_id: str) -> dict:
    record = read(task_id)
    artifacts = record.get("artifacts", {})
    def art(name):
        return artifacts.get(name, {}).get("data")
    report = {
        "task_id": task_id,
        "task": record.get("task"),
        "status": record.get("status"),
        "repo_path": record.get("repo_path"),
        "workspace_path": record.get("workspace_path"),
        "summary": {
            "has_context": "relevant_context" in artifacts,
            "has_patch": "patch_apply" in artifacts or "patch_recorded" in artifacts,
            "has_tests": "test_result" in artifacts,
            "has_quality": "quality_result" in artifacts,
            "has_review": "review_checklist" in artifacts or "diff_summary" in artifacts,
            "has_policy": "policy_result" in artifacts,
        },
        "tests": art("test_result"),
        "quality": art("quality_result"),
        "diff_summary": art("diff_summary"),
        "risk_report": art("risk_report"),
        "policy": art("policy_result"),
        "events_count": len(record.get("events", [])),
        "artifact_names": sorted(artifacts.keys()),
    }
    return report


def status_summary() -> dict:
    records = list_tasks().get("tasks", [])
    counts: dict[str, int] = {}
    for r in records:
        counts[r.get("status") or "unknown"] = counts.get(r.get("status") or "unknown", 0) + 1
    return {"count": len(records), "by_status": counts, "tasks": records[:200]}


def gc(max_age_ms: int = 7 * 24 * 60 * 60 * 1000, statuses: list[str] | None = None, dry_run: bool = True) -> dict:
    statuses = statuses or ["cancelled", "finalized"]
    now = _now()
    candidates = []
    for path in sorted(_ledger_root().glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        age = now - int(record.get("updated_at") or record.get("created_at") or now)
        if record.get("status") in statuses and age >= max_age_ms:
            candidates.append({"task_id": record.get("task_id"), "status": record.get("status"), "age_ms": age, "path": str(path)})
            if not dry_run:
                path.unlink(missing_ok=True)
    return {"dry_run": dry_run, "candidates": candidates, "count": len(candidates)}


def lock_ttl(task_id: str, owner: str = "coding-gpt", ttl_ms: int = 30 * 60 * 1000) -> dict:
    record = read(task_id)
    now = _now()
    locked_by = record.get("locked_by")
    expires = int(record.get("lock_expires_at") or 0)
    if locked_by and locked_by != owner and expires > now:
        raise PolicyError("task_locked", f"Task is locked by {locked_by} until {expires}")
    record["locked_by"] = owner
    record["lock_expires_at"] = now + ttl_ms
    record["updated_at"] = now
    _task_path(task_id).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def artifact_index(task_id: str) -> dict:
    record = read(task_id)
    items = []
    for name, payload in record.get("artifacts", {}).items():
        data = payload.get("data")
        try:
            size = len(json.dumps(data))
        except Exception:
            size = 0
        items.append({"name": name, "timestamp": payload.get("timestamp"), "approx_size_bytes": size})
    return {"task_id": task_id, "artifacts": items, "count": len(items)}


REQUIRED_FINAL_ARTIFACTS = ["relevant_context", "patch_recorded", "test_result", "quality_result", "diff_summary", "risk_report", "review_checklist", "policy_result"]


def validate_required_artifacts(task_id: str, required: list[str] | None = None) -> dict:
    record = read(task_id)
    artifacts = record.get("artifacts", {})
    required = required or REQUIRED_FINAL_ARTIFACTS
    missing = [name for name in required if name not in artifacts]
    present = [name for name in required if name in artifacts]
    return {"task_id": task_id, "valid": not missing, "present": present, "missing": missing, "artifact_names": sorted(artifacts.keys())}


def phase_contract(task_id: str) -> dict:
    record = read(task_id)
    artifacts = record.get("artifacts", {})
    workspace = record.get("workspace_path")
    if not workspace:
        phase = "need_workspace"
        contract = {"allowed_submission": "workspace_path", "must_call": ["/workspace/create", "/tasks/update"], "gpt_instruction": "Create an isolated worktree. Do not patch the primary checkout."}
    elif "relevant_context" not in artifacts:
        phase = "need_context"
        contract = {"allowed_submission": "artifact", "artifact_name": "relevant_context", "must_call": ["/repo/instructions", "/repo/relevant-context", "/agent/coding-task/submit"], "gpt_instruction": "Gather repo instructions and relevant files. Submit them as relevant_context before creating a patch."}
    elif "patch_recorded" not in artifacts:
        phase = "need_patch"
        contract = {"allowed_submission": "unified_diff", "must_call": ["/agent/coding-task/submit"], "gpt_instruction": "Return a minimal unified diff only. No prose in the patch payload. The submit endpoint will risk-check, preview, record, and apply it."}
    elif "test_result" not in artifacts:
        phase = "need_tests"
        contract = {"allowed_submission": "run_tests", "must_call": ["/agent/coding-task/submit"], "gpt_instruction": "Run discovered tests through submit with run_tests=true. Do not run arbitrary commands."}
    elif artifacts.get("test_result", {}).get("data", {}).get("passed") is False:
        phase = "need_repair"
        contract = {"allowed_submission": "repair_patch", "must_call": ["/agent/coding-task/repair-plan", "/repo/read-context", "/agent/coding-task/submit"], "gpt_instruction": "Use repair-plan and diagnostics before patching. Patch only the likely failure area."}
    elif "quality_result" not in artifacts:
        phase = "need_quality"
        contract = {"allowed_submission": "run_quality", "must_call": ["/agent/coding-task/submit"], "gpt_instruction": "Run quality checks through submit with run_quality=true."}
    elif artifacts.get("quality_result", {}).get("data", {}).get("passed") is False:
        phase = "need_quality_repair"
        contract = {"allowed_submission": "quality_repair_patch", "must_call": ["/agent/coding-task/repair-plan", "/agent/coding-task/submit"], "gpt_instruction": "Repair quality failures minimally, then rerun quality checks."}
    elif "diff_summary" not in artifacts or "review_checklist" not in artifacts:
        phase = "need_review"
        contract = {"allowed_submission": "review_artifacts", "must_call": ["/agent/coding-task/finalize"], "gpt_instruction": "Finalize will attach diff summary, risk report, review checklist, policy result, and optional commit/PR dry-run."}
    else:
        phase = "ready_to_finalize"
        contract = {"allowed_submission": "finalize", "must_call": ["/agent/coding-task/finalize"], "gpt_instruction": "Finalize with exact tests run, risks, and policy status. Do not claim success without passing checks."}
    return {"task_id": task_id, "phase": phase, "contract": contract, "validation": validate_required_artifacts(task_id)}


def iteration_summary(task_id: str) -> dict:
    record = read(task_id)
    artifacts = record.get("artifacts", {})
    patches = artifacts.get("patch_recorded", {}).get("data", {})
    tests = artifacts.get("test_result", {}).get("data", {})
    quality = artifacts.get("quality_result", {}).get("data", {})
    diagnostics = artifacts.get("diagnostics", {}).get("data", {})
    return {
        "task_id": task_id,
        "status": record.get("status"),
        "phase": phase_contract(task_id).get("phase"),
        "patch_applied": bool(patches.get("applied")),
        "files_touched": patches.get("files_touched") or [],
        "tests_passed": tests.get("passed"),
        "quality_passed": quality.get("passed"),
        "diagnostic_count": diagnostics.get("count", 0) if isinstance(diagnostics, dict) else 0,
        "next_instruction": phase_contract(task_id).get("contract", {}).get("gpt_instruction"),
        "artifact_validation": validate_required_artifacts(task_id),
    }

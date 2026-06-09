from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from evals import report as eval_report
from evals import case_loader
from evals import regression_loader
from utils import eval_telemetry
from utils.auth import verify_key

router = APIRouter(dependencies=[Depends(verify_key)])

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REGRESSION_ROOT = _REPO_ROOT / "evals" / "regressions"
_BUILTIN_CASES = [
    {
        "id": "core_smoke",
        "suite": "core_smoke",
        "description": "Safely validates the uploadable Coding GPT core workflow and dispatcher endpoints.",
        "safe_only": True,
        "endpoint": "/agent/coding-task/smoke-test",
    },
    {
        "id": "payload_recovery",
        "suite": "payload_recovery",
        "description": "Verifies missing_payload_fields returns required payload metadata and an example payload.",
        "safe_only": True,
        "endpoint": "/coding/repo/action",
    },
]




class EvalReleaseGateRequest(BaseModel):
    repo_path: str = Field(..., description="Repository path to evaluate, e.g. /home/obsidian/Elevate_test.")
    run_id: str | None = None
    require_clean_git: bool = True

class EvalRunRequest(BaseModel):
    suite: str = Field("core_smoke", description="Evaluation suite to run. Supported: core_smoke, payload_recovery, release_gate, regressions, phase6_regressions.")
    repo_path: str = Field(..., description="Repository path to evaluate, e.g. /home/obsidian/Elevate_test.")
    safe_only: bool = True
    report_id: str | None = None


class EvalReportRequest(BaseModel):
    task_id: str | None = None
    run_id: str | None = None
    events_path: str | None = None
    report_id: str | None = None


class EvalCompareRequest(BaseModel):
    current_run_id: str | None = None
    baseline_run_id: str | None = None
    current_report_id: str | None = None
    baseline_report_id: str | None = None


class RegressionCreateRequest(BaseModel):
    id: str
    title: str
    failure_layer: str = "unknown"
    symptom: str
    expected_behavior: str
    source: str = "manual"
    details: dict[str, Any] = Field(default_factory=dict)


def _now_id(prefix: str) -> str:
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 10000:04d}"


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-._")[:120]
    return slug or "regression"


def _report_path(report_id: str, suffix: str) -> Path:
    return eval_telemetry.eval_root() / "reports" / f"{report_id}.{suffix}"


def _load_report_by_id(report_id: str) -> dict[str, Any]:
    path = _report_path(report_id, "json")
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {report_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _events_since(start_ms: int, *, run_id: str | None = None) -> list[dict[str, Any]]:
    events = eval_report.load_events()
    out = []
    for event in events:
        ts = event.get("timestamp")
        if isinstance(ts, int) and ts >= start_ms:
            if run_id is None or event.get("run_id") in (None, run_id):
                out.append(event)
    return out


def _write_report_for_events(events: list[dict[str, Any]], report_id: str) -> dict[str, Any]:
    report = eval_report.build_report(events, report_id=report_id, source_path=str(eval_telemetry.events_path()))
    json_path = eval_report.write_json_report(report)
    md_path = eval_report.write_markdown_report(report)
    report["summary"]["report_json"] = str(json_path)
    report["summary"]["report_md"] = str(md_path)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary", {})
    return {
        "report_id": summary.get("report_id"),
        "event_count": summary.get("event_count"),
        "agent_score": report.get("scores", {}).get("agent", {}).get("score"),
        "backend_score": report.get("scores", {}).get("backend", {}).get("score"),
        "failures": len(report.get("failures", [])),
        "recommendations": report.get("recommendations", [])[:5],
        "report_json": summary.get("report_json"),
        "report_md": summary.get("report_md"),
    }


def _run_core_smoke(repo_path: str, *, run_id: str | None = None) -> dict[str, Any]:
    from routes.coding_agent import CodingTaskSmokeTestRequest, coding_task_smoke_test

    unique = run_id or _now_id("core_smoke")
    return coding_task_smoke_test(CodingTaskSmokeTestRequest(
        repo_path=repo_path,
        safe_only=True,
        task=f"Smoke-test all uploadable Coding GPT core endpoints safely {unique}",
    ))


def _run_payload_recovery(repo_path: str) -> dict[str, Any]:
    from routes import coding_dispatch

    first = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="instructions", payload={}))
    example = ((first.get("error") or {}).get("example_payload") or {"repo_path": repo_path}) if isinstance(first, dict) else {"repo_path": repo_path}
    if "repo_path" not in example:
        example["repo_path"] = repo_path
    second = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="instructions", payload=example))
    return {
        "status": 200 if first.get("status") == 400 and (second.get("status") == 200 or isinstance(second.get("status"), str)) else 400,
        "first_call": first,
        "retry_payload": example,
        "second_call_status": second.get("status") if isinstance(second, dict) else None,
        "passed": first.get("status") == 400 and (second.get("status") == 200 or isinstance(second.get("status"), str)),
    }


def _run_suite(suite: str, repo_path: str, *, run_id: str | None = None) -> dict[str, Any]:
    if suite in {"regressions", "phase6_regressions"}:
        return regression_loader.run_all(repo_path=repo_path, run_id=run_id)
    declarative = case_loader.cases_for_suite(suite)
    if declarative:
        return case_loader.run_suite(suite, repo_path=repo_path, run_id=run_id)
    if suite == "core_smoke":
        return _run_core_smoke(repo_path, run_id=run_id)
    if suite == "payload_recovery":
        return _run_payload_recovery(repo_path)
    if suite == "release_gate":
        core = _run_core_smoke(repo_path, run_id=run_id)
        payload = _run_payload_recovery(repo_path)
        core_failed = ((core.get("smoke_test") or {}).get("failed") or 0) if isinstance(core, dict) else 1
        passed = core.get("status") == 200 and core_failed == 0 and payload.get("passed") is True
        return {"status": 200 if passed else 400, "passed": passed, "core_smoke": core, "payload_recovery": payload}
    available = sorted({c.get("suite") for c in case_loader.list_cases() if c.get("suite")} | {c.get("id") for c in case_loader.list_cases() if c.get("id")} | {"core_smoke", "payload_recovery", "release_gate"})
    return {"status": 400, "error": {"code": "unsupported_suite", "message": f"Supported suites/cases: {', '.join(available)}"}}


@router.get("/cases")
def list_eval_cases():
    regression_files = []
    if _REGRESSION_ROOT.exists():
        regression_files = regression_loader.list_regressions()
    declarative_cases = case_loader.list_cases()
    suite_names = set()
    for c in declarative_cases:
        if c.get("suite"):
            suite_names.add(c.get("suite"))
        for name in c.get("suites") or []:
            suite_names.add(name)
    suites = sorted(suite_names)
    suites = sorted(set(suites) | {"regressions", "phase6_regressions"})
    return {"status": 200, "builtin_cases": _BUILTIN_CASES, "declarative_cases": declarative_cases, "suites": suites, "regressions": regression_files}


@router.post("/run")
def run_eval(req: EvalRunRequest):
    run_id = req.report_id or _now_id(f"eval_{_safe_slug(req.suite)}")
    start_ms = int(time.time() * 1000)
    eval_telemetry.log_event("eval_run_started", run_id=run_id, suite=req.suite, repo_path=req.repo_path, safe_only=req.safe_only)
    result = _run_suite(req.suite, req.repo_path, run_id=run_id)
    eval_telemetry.log_event("eval_run_completed", run_id=run_id, suite=req.suite, repo_path=req.repo_path, status=result.get("status"), passed=result.get("passed"))
    events = _events_since(start_ms)
    report = _write_report_for_events(events, run_id)
    summary = _summarize_report(report)
    return {"status": result.get("status", 200), "run_id": run_id, "suite": req.suite, "result": result, "report": summary}


@router.post("/report")
def generate_or_read_report(req: EvalReportRequest):
    if req.report_id and not (req.task_id or req.run_id or req.events_path):
        report = _load_report_by_id(req.report_id)
        return {"status": 200, "report": _summarize_report(report), "full_report": report}
    report = eval_report.generate_report(req.events_path, task_id=req.task_id, run_id=req.run_id, report_id=req.report_id)
    return {"status": 200, "report": _summarize_report(report), "full_report": report}


@router.post("/compare")
def compare_reports(req: EvalCompareRequest):
    current_id = req.current_report_id or req.current_run_id
    baseline_id = req.baseline_report_id or req.baseline_run_id
    if not current_id or not baseline_id:
        return {"status": 400, "error": {"code": "missing_report_ids", "message": "Provide current and baseline report/run ids."}}
    try:
        current = _load_report_by_id(current_id)
        baseline = _load_report_by_id(baseline_id)
    except FileNotFoundError as exc:
        return {"status": 404, "error": {"code": "report_not_found", "message": str(exc)}}
    def score(report: dict[str, Any], section: str) -> int:
        return int(report.get("scores", {}).get(section, {}).get("score") or 0)
    current_failures = {f.get("code") for f in current.get("failures", [])}
    baseline_failures = {f.get("code") for f in baseline.get("failures", [])}
    comparison = {
        "current": _summarize_report(current),
        "baseline": _summarize_report(baseline),
        "deltas": {
            "agent_score": score(current, "agent") - score(baseline, "agent"),
            "backend_score": score(current, "backend") - score(baseline, "backend"),
            "failure_count": len(current.get("failures", [])) - len(baseline.get("failures", [])),
        },
        "new_failure_codes": sorted(current_failures - baseline_failures),
        "fixed_failure_codes": sorted(baseline_failures - current_failures),
    }
    return {"status": 200, "comparison": comparison}


@router.get("/regressions")
def list_regressions():
    items = regression_loader.list_regressions()
    return {"status": 200, "regressions": items, "count": len(items)}


@router.post("/regressions")
def create_regression(req: RegressionCreateRequest):
    _REGRESSION_ROOT.mkdir(parents=True, exist_ok=True)
    slug = _safe_slug(req.id)
    path = _REGRESSION_ROOT / f"{slug}.yaml"
    payload = {
        "id": req.id,
        "title": req.title,
        "source": req.source,
        "failure_layer": req.failure_layer,
        "symptom": req.symptom,
        "expected_behavior": req.expected_behavior,
        "details": req.details,
        "created_at": int(time.time() * 1000),
    }
    text = "\n".join([
        f"id: {json.dumps(payload['id'])}",
        f"title: {json.dumps(payload['title'])}",
        f"source: {json.dumps(payload['source'])}",
        f"failure_layer: {json.dumps(payload['failure_layer'])}",
        f"symptom: {json.dumps(payload['symptom'])}",
        f"expected_behavior: {json.dumps(payload['expected_behavior'])}",
        f"created_at: {payload['created_at']}",
        "details_json: |",
        *["  " + line for line in json.dumps(payload["details"], indent=2, sort_keys=True).splitlines()],
        "",
    ])
    path.write_text(text, encoding="utf-8")
    eval_telemetry.log_event("regression_created", regression_id=req.id, failure_layer=req.failure_layer, path=str(path))
    return {"status": 200, "regression": {"id": req.id, "path": str(path), "relative_path": str(path.relative_to(_REPO_ROOT))}}




@router.post("/release-gate")
def run_release_gate_endpoint(req: EvalReleaseGateRequest):
    from evals.run_release_gate import run_release_gate

    result = run_release_gate(req.repo_path, run_id=req.run_id, require_clean_git=req.require_clean_git)
    return {
        "status": result.get("status"),
        "run_id": result.get("run_id"),
        "total": result.get("total"),
        "passed": result.get("passed"),
        "failed": result.get("failed"),
        "failed_blockers": result.get("failed_blockers"),
        "agent_score": (result.get("eval_report") or {}).get("agent_score"),
        "backend_score": (result.get("eval_report") or {}).get("backend_score"),
        "release_gate_json": result.get("release_gate_json"),
        "release_gate_md": result.get("release_gate_md"),
        "eval_report": result.get("eval_report"),
    }


class DebugLogIngestRequest(BaseModel):
    log_text: str = Field(..., description="Pasted Custom GPT Actions debug transcript.")
    source: str = "custom_gpt_debug"
    run_id: str | None = None
    write_events: bool = True
    create_regression: bool = False
    regression_title: str | None = None


@router.post("/ingest-debug-log")
def ingest_debug_log(req: DebugLogIngestRequest):
    from evals import debug_ingest

    run_id = req.run_id or _now_id("debug_ingest")
    parsed = debug_ingest.classify_debug_log(req.log_text)
    paths = debug_ingest.write_ingest_report(parsed, run_id=run_id)
    events_written = 0
    if req.write_events:
        for event in debug_ingest.debug_log_to_events(req.log_text, run_id=run_id, source=req.source):
            eval_telemetry.log_event(**event)
            events_written += 1
    regression = None
    if req.create_regression:
        payload = debug_ingest.regression_from_debug(parsed, title=req.regression_title, source=req.source)
        create_req = RegressionCreateRequest(**payload)
        regression = create_regression(create_req).get("regression")
    return {
        "status": 200,
        "run_id": run_id,
        "parsed": {
            "call_count": parsed.get("call_count"),
            "successful_calls": parsed.get("successful_calls"),
            "failed_calls": parsed.get("failed_calls"),
            "agent_behavior_score": parsed.get("agent_behavior_score"),
            "failure_codes": parsed.get("failure_codes"),
            "failure_layers": parsed.get("failure_layers"),
            "warnings": parsed.get("warnings"),
        },
        "calls": parsed.get("calls"),
        "events_written": events_written,
        "reports": paths,
        "regression": regression,
    }


@router.post("/debug-log/regression")
def create_regression_from_debug_log(req: DebugLogIngestRequest):
    from evals import debug_ingest

    parsed = debug_ingest.classify_debug_log(req.log_text)
    payload = debug_ingest.regression_from_debug(parsed, title=req.regression_title, source=req.source)
    result = create_regression(RegressionCreateRequest(**payload))
    return {"status": 200, "regression": result.get("regression"), "source_summary": {"failure_codes": parsed.get("failure_codes"), "failure_layers": parsed.get("failure_layers"), "call_count": parsed.get("call_count")}}

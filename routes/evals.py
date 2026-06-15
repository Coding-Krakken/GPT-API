from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from evals import report as eval_report
from evals import dashboard as eval_dashboard
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






class EvalContinuousLearningRequest(BaseModel):
    repo_path: str = Field(..., description="Repository path to evaluate, e.g. /home/obsidian/Elevate_test.")
    run_id: str | None = None
    baseline_report_id: str | None = None
    require_clean_git: bool = True

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


class EvalRecommendationsRequest(BaseModel):
    report_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    events_path: str | None = None
    top_n: int = 10


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
        "recommendation_summary": (report.get("recommendation_engine") or {}).get("summary", {}),
        "recommendations": report.get("recommendations", [])[:5],
        "recommendations_grouped": {k: v[:3] for k, v in (report.get("recommendations_grouped") or {}).items()},
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




@router.get("/dashboard", response_class=HTMLResponse)
def eval_dashboard_html(limit: int = Query(25, ge=1, le=200)):
    return HTMLResponse(eval_dashboard.render_html(limit=limit))


@router.get("/dashboard.md", response_class=PlainTextResponse)
def eval_dashboard_markdown(limit: int = Query(25, ge=1, le=200)):
    return PlainTextResponse(eval_dashboard.render_markdown(limit=limit), media_type="text/markdown")


@router.get("/dashboard/summary")
def eval_dashboard_summary(limit: int = Query(25, ge=1, le=200), repo_path: str | None = None, task_id: str | None = None, min_agent_score: int | None = None, min_backend_score: int | None = None, failure_layer: str | None = None, endpoint: str | None = None):
    return eval_dashboard.list_reports(limit=limit, repo_path=repo_path, task_id=task_id, min_agent_score=min_agent_score, min_backend_score=min_backend_score, failure_layer=failure_layer, endpoint=endpoint)


@router.get("/dashboard/latest")
def eval_dashboard_latest():
    return eval_dashboard.latest_report()


@router.get("/dashboard/trend")
def eval_dashboard_trend(limit: int = Query(20, ge=1, le=200)):
    return eval_dashboard.trend(limit=limit)


@router.get("/dashboard/report/{report_id}")
def eval_dashboard_report_detail(report_id: str):
    try:
        report = eval_dashboard.load_report(report_id)
        return {"status": 200, "report": report}
    except FileNotFoundError as exc:
        return {"status": 404, "error": {"code": "report_not_found", "message": str(exc)}}
    except ValueError as exc:
        return {"status": 400, "error": {"code": "invalid_report", "message": str(exc)}}


@router.get("/dashboard/compare")
def eval_dashboard_compare(current_report_id: str, baseline_report_id: str):
    try:
        return eval_dashboard.compare(current_report_id, baseline_report_id)
    except FileNotFoundError as exc:
        return {"status": 404, "error": {"code": "report_not_found", "message": str(exc)}}
    except ValueError as exc:
        return {"status": 400, "error": {"code": "invalid_report", "message": str(exc)}}


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


@router.post("/recommendations")
def generate_recommendations_endpoint(req: EvalRecommendationsRequest):
    if req.report_id and not (req.task_id or req.run_id or req.events_path):
        try:
            report = _load_report_by_id(req.report_id)
        except FileNotFoundError as exc:
            return {"status": 404, "error": {"code": "report_not_found", "message": str(exc)}}
    else:
        report = eval_report.generate_report(req.events_path, task_id=req.task_id, run_id=req.run_id, report_id=req.report_id)
    rec_engine = report.get("recommendation_engine") or {}
    ranked = (rec_engine.get("ranked") or report.get("recommendations") or [])[: max(1, min(req.top_n, 50))]
    grouped = rec_engine.get("grouped") or report.get("recommendations_grouped") or {}
    return {
        "status": 200,
        "report_id": report.get("summary", {}).get("report_id"),
        "summary": rec_engine.get("summary", {}),
        "top_recommendations": ranked,
        "grouped": grouped,
        "report_json": report.get("summary", {}).get("report_json"),
        "report_md": report.get("summary", {}).get("report_md"),
    }


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






@router.post("/continuous-learning")
def run_continuous_learning_endpoint(req: EvalContinuousLearningRequest):
    from evals.continuous_learning import run_continuous_learning_cycle

    result = run_continuous_learning_cycle(
        req.repo_path,
        run_id=req.run_id,
        baseline_report_id=req.baseline_report_id,
        require_clean_git=req.require_clean_git,
    )
    return {
        "status": result.get("status"),
        "run_id": result.get("run_id"),
        "ship_ready": (result.get("ship_decision") or {}).get("ship_ready"),
        "blockers": (result.get("ship_decision") or {}).get("blockers"),
        "warnings": (result.get("ship_decision") or {}).get("warnings"),
        "current_report_id": result.get("current_report_id"),
        "baseline_report_id": result.get("baseline_report_id"),
        "release_gate_status": (result.get("release_gate") or {}).get("status"),
        "agent_score": ((result.get("release_gate") or {}).get("eval_report") or {}).get("agent_score"),
        "backend_score": ((result.get("release_gate") or {}).get("eval_report") or {}).get("backend_score"),
        "regression_coverage": result.get("regression_coverage"),
        "continuous_learning_json": result.get("continuous_learning_json"),
        "continuous_learning_md": result.get("continuous_learning_md"),
    }


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


class EvalPhase13Request(BaseModel):
    repo_path: str = Field(..., description="Repository path to evaluate, e.g. /home/obsidian/Elevate_test.")
    run_id: str | None = None
    baseline_report_id: str | None = None
    promote_baseline: bool = False
    create_bundle: bool = True
    require_clean_git: bool = True
    blocking: bool = False
    timeout_seconds: int = 15


@router.get("/phase13/status")
def phase13_status(require_clean_git: bool = Query(True)):
    from evals.phase13_ops import operational_readiness

    return operational_readiness(require_clean_git=require_clean_git)


def _phase13_job_paths(run_id: str) -> dict[str, str]:
    root = eval_telemetry.eval_root() / "phase13"
    jobs = root / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    return {
        "job_json": str(jobs / f"{run_id}.json"),
        "job_log": str(jobs / f"{run_id}.log"),
        "phase13_json": str(root / f"{run_id}.json"),
        "phase13_md": str(root / f"{run_id}.md"),
    }


def _read_phase13_job(run_id: str) -> dict[str, Any]:
    paths = _phase13_job_paths(run_id)
    job_path = Path(paths["job_json"])
    phase_path = Path(paths["phase13_json"])
    if phase_path.exists():
        try:
            result = json.loads(phase_path.read_text(encoding="utf-8"))
            return {"status": 200, "job_status": "completed", "run_id": run_id, "result": result, **paths}
        except Exception as exc:
            return {"status": 500, "job_status": "invalid_result", "run_id": run_id, "error": {"code": "invalid_phase13_result", "message": str(exc)}, **paths}
    if job_path.exists():
        try:
            job = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            job = {"job_status": "unknown", "run_id": run_id}
        pid = job.get("pid")
        if pid and Path(f"/proc/{pid}").exists():
            job["job_status"] = "running"
            job["status"] = 202
        else:
            job["job_status"] = job.get("job_status") or "exited_without_result"
            job["status"] = 500
        job.update(paths)
        return job
    return {"status": 404, "job_status": "not_found", "run_id": run_id, "error": {"code": "phase13_job_not_found", "message": f"No Phase 13 job/result found for {run_id}"}, **paths}


def _start_phase13_job(req: EvalPhase13Request, run_id: str) -> dict[str, Any]:
    paths = _phase13_job_paths(run_id)
    args = [sys.executable, str(_REPO_ROOT / "evals" / "phase13_ops.py"), "--repo-path", req.repo_path, "--run-id", run_id]
    if req.baseline_report_id:
        args.extend(["--baseline-report-id", req.baseline_report_id])
    if req.promote_baseline:
        args.append("--promote")
    if not req.create_bundle:
        args.append("--no-bundle")
    if not req.require_clean_git:
        args.append("--allow-dirty")
    job = {
        "status": 202,
        "job_status": "running",
        "run_id": run_id,
        "repo_path": req.repo_path,
        "started_at": int(time.time() * 1000),
        "command": args,
        **paths,
    }
    Path(paths["job_json"]).write_text(json.dumps(job, indent=2, sort_keys=True), encoding="utf-8")
    log_fh = open(paths["job_log"], "ab")
    proc = subprocess.Popen(args, cwd=str(_REPO_ROOT), stdout=log_fh, stderr=subprocess.STDOUT, start_new_session=True, env=os.environ.copy())
    log_fh.close()
    job["pid"] = proc.pid
    Path(paths["job_json"]).write_text(json.dumps(job, indent=2, sort_keys=True), encoding="utf-8")
    eval_telemetry.log_event("phase13_job_started", run_id=run_id, repo_path=req.repo_path, pid=proc.pid, job_json=paths["job_json"], job_log=paths["job_log"])
    return job


@router.post("/phase13/run")
def run_phase13_endpoint(req: EvalPhase13Request):
    from evals.phase13_ops import run_phase13_production_ops

    run_id = req.run_id or _now_id("phase13")
    if not req.blocking:
        existing = _read_phase13_job(run_id)
        if existing.get("status") in {200, 202}:
            return existing
        return _start_phase13_job(req, run_id)

    result = run_phase13_production_ops(
        req.repo_path,
        run_id=run_id,
        baseline_report_id=req.baseline_report_id,
        promote=req.promote_baseline,
        create_bundle=req.create_bundle,
        require_clean_git=req.require_clean_git,
    )
    return {
        "status": result.get("status"),
        "job_status": "completed",
        "phase13_complete": result.get("phase13_complete"),
        "version": result.get("version"),
        "run_id": result.get("run_id"),
        "ship_ready": (result.get("ship_decision") or {}).get("ship_ready"),
        "blockers": (result.get("ship_decision") or {}).get("blockers"),
        "warnings": (result.get("ship_decision") or {}).get("warnings"),
        "current_report_id": result.get("current_report_id"),
        "baseline_report_id": result.get("baseline_report_id"),
        "readiness": result.get("readiness"),
        "continuous_learning_md": result.get("continuous_learning_md"),
        "phase13_json": result.get("phase13_json"),
        "phase13_md": result.get("phase13_md"),
        "baseline_promotion": result.get("baseline_promotion"),
        "release_bundle": {
            "status": (result.get("release_bundle") or {}).get("status"),
            "bundle_archive": (result.get("release_bundle") or {}).get("bundle_archive"),
            "bundle_dir": (result.get("release_bundle") or {}).get("bundle_dir"),
        } if result.get("release_bundle") else None,
    }


@router.get("/phase13/job/{run_id}")
def phase13_job_status(run_id: str):
    return _read_phase13_job(run_id)


class EvalPhase13PromoteRequest(BaseModel):
    report_id: str
    run_id: str | None = None
    reason: str = "manual Phase 13 baseline promotion"


@router.post("/phase13/promote-baseline")
def phase13_promote_baseline(req: EvalPhase13PromoteRequest):
    from evals.phase13_ops import promote_baseline

    return promote_baseline(req.report_id, run_id=req.run_id, reason=req.reason)

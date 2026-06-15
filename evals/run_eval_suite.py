from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals import case_loader, report as eval_report
from utils import eval_telemetry

DEFAULT_REPO = "/home/obsidian/Elevate_test"


def run_suite(suite: str, repo_path: str, report_id: str | None = None) -> dict[str, Any]:
    run_id = report_id or f"suite_{suite}_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%10000:04d}"
    start_ms = int(time.time() * 1000)
    eval_telemetry.log_event("eval_suite_started", run_id=run_id, suite=suite, repo_path=repo_path)
    result = case_loader.run_suite(suite, repo_path=repo_path, run_id=run_id)
    eval_telemetry.log_event("eval_suite_completed", run_id=run_id, suite=suite, repo_path=repo_path, status=result.get("status"), passed=result.get("failed") == 0)
    events = [e for e in eval_report.load_events() if isinstance(e.get("timestamp"), int) and e.get("timestamp") >= start_ms and e.get("run_id") in (run_id, None)]
    report = eval_report.build_report(events, report_id=run_id, source_path=str(eval_telemetry.events_path()))
    report.setdefault("suite_result", result)
    json_path = eval_report.write_json_report(report)
    md_path = eval_report.write_markdown_report(report)
    report["summary"]["report_json"] = str(json_path)
    report["summary"]["report_md"] = str(md_path)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return {"run_id": run_id, "suite": suite, "result": result, "report_json": str(json_path), "report_md": str(md_path), "agent_score": report["scores"]["agent"]["score"], "backend_score": report["scores"]["backend"]["score"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Coding GPT Phase 5 evaluation suites")
    parser.add_argument("--suite", default="phase5_full", help="Suite name or case id. Examples: core_smoke, payload_discipline, policy_safety, repo_intelligence, coding_task_quality, phase5_full, release_gate")
    parser.add_argument("--repo-path", default=DEFAULT_REPO)
    parser.add_argument("--report-id", default=None)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps({"cases": case_loader.list_cases()}, indent=2))
        return 0
    result = run_suite(args.suite, args.repo_path, args.report_id)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["result"].get("failed", 1) == 0 and result["result"].get("status") == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())

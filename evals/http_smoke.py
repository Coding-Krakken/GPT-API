from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_REPO = "/home/obsidian/Elevate_test"
DEFAULT_BASE = "http://127.0.0.1:8000"


def _load_key(env_file: Path) -> str:
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("API_KEY="):
            return line.split("=", 1)[1]
    return ""


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def run_http_smoke(
    *,
    base_url: str = DEFAULT_BASE,
    repo_path: str = DEFAULT_REPO,
    api_key: str,
    report_path: Path,
    run_id: str,
    include_phase13_job: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "stage": "begin",
        "base_url": base_url,
        "repo_path": repo_path,
        "run_id": run_id,
        "used_api_key": bool(api_key),
        "checks": checks,
    }

    def update(stage: str) -> None:
        report["stage"] = stage
        report["total"] = len(checks)
        report["passed"] = sum(1 for c in checks if c.get("ok") is True)
        report["failed"] = sum(1 for c in checks if c.get("ok") is False)
        _write_report(report_path, report)

    def call(name: str, method: str, path: str, body: dict[str, Any] | None = None, *, timeout: int = 60, expect_body_status: int | None = None, ok_http: tuple[int, ...] = (200,)) -> dict[str, Any]:
        item = {"name": name, "method": method, "path": path, "stage": "started", "ok": None, "started_at": int(time.time() * 1000)}
        checks.append(item)
        update(f"started_{name}")
        headers = {"x-api-key": api_key} if api_key else {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["content-type"] = "application/json"
        started = time.time()
        try:
            req = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = {"raw": raw[:1200]}
                body_status = parsed.get("status") if isinstance(parsed, dict) else None
                ok = resp.status in ok_http and (expect_body_status is None or body_status == expect_body_status)
                item.update({"stage": "done", "http_status": resp.status, "body_status": body_status, "ok": bool(ok), "elapsed_ms": round((time.time() - started) * 1000, 2), "preview": json.dumps(parsed, default=str)[:1600]})
                update(f"finished_{name}")
                return parsed if isinstance(parsed, dict) else {"raw": parsed}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"raw": raw[:1200]}
            body_status = parsed.get("status") if isinstance(parsed, dict) else None
            ok = exc.code in ok_http and (expect_body_status is None or body_status == expect_body_status)
            item.update({"stage": "http_error", "http_status": exc.code, "body_status": body_status, "ok": bool(ok), "elapsed_ms": round((time.time() - started) * 1000, 2), "preview": json.dumps(parsed, default=str)[:1600]})
            update(f"finished_{name}")
            return parsed if isinstance(parsed, dict) else {"raw": parsed}
        except Exception as exc:
            item.update({"stage": "exception", "ok": False, "error": type(exc).__name__, "message": str(exc), "elapsed_ms": round((time.time() - started) * 1000, 2)})
            update(f"finished_{name}")
            return {"error": {"code": type(exc).__name__, "message": str(exc)}}

    update("begin")
    call("schema_core_yaml", "GET", "/coding-gpt-core-openapi.yaml", timeout=20, expect_body_status=None)
    call("phase13_status", "GET", "/evals/phase13/status?require_clean_git=true", timeout=60, expect_body_status=200)
    call("dispatcher_missing_payload_hint", "POST", "/coding/repo/action", {"action": "instructions", "payload": {}}, timeout=30, expect_body_status=400)
    call("dispatcher_retry_payload", "POST", "/coding/repo/action", {"action": "instructions", "payload": {"repo_path": repo_path}}, timeout=30, expect_body_status=200)
    call("eval_run_payload_recovery", "POST", "/evals/run", {"suite": "payload_recovery", "repo_path": repo_path, "safe_only": True, "report_id": f"{run_id}_payload_recovery"}, timeout=120, expect_body_status=200)
    call("coding_smoke_test", "POST", "/agent/coding-task/smoke-test", {"repo_path": repo_path, "safe_only": True, "task": f"HTTP smoke {run_id}"}, timeout=180, expect_body_status=200)
    call("eval_release_gate", "POST", "/evals/release-gate", {"repo_path": repo_path, "run_id": f"{run_id}_release_gate", "require_clean_git": True}, timeout=240, expect_body_status=200)
    if include_phase13_job:
        phase13_run_id = f"{run_id}_phase13"
        start = call("phase13_job_start", "POST", "/evals/phase13/run", {"repo_path": repo_path, "run_id": phase13_run_id, "promote_baseline": False, "create_bundle": False, "require_clean_git": True}, timeout=30, expect_body_status=202)
        # Poll until completed or bounded timeout. The job runs outside the HTTP request.
        for attempt in range(60):
            status = call(f"phase13_job_poll_{attempt+1}", "GET", f"/evals/phase13/job/{phase13_run_id}", timeout=20, expect_body_status=None)
            if status.get("job_status") == "completed":
                checks[-1]["ok"] = status.get("status") == 200
                break
            time.sleep(2)
        else:
            checks.append({"name": "phase13_job_poll_timeout", "method": "GET", "path": f"/evals/phase13/job/{phase13_run_id}", "ok": False, "stage": "timeout", "message": "Phase 13 job did not complete within polling window."})
            update("phase13_job_poll_timeout")
    # Auth negative check
    wrong_key = api_key + "-wrong" if api_key else "definitely-wrong-key"
    original_key = api_key
    api_key = wrong_key
    # manual wrong-key call because nested function captures api_key as local after assignment.
    item = {"name": "auth_rejects_wrong_key", "method": "GET", "path": "/evals/phase13/status", "stage": "started", "ok": None}
    checks.append(item)
    update("started_auth_rejects_wrong_key")
    try:
        req = urllib.request.Request(base_url.rstrip("/") + "/evals/phase13/status?require_clean_git=false", headers={"x-api-key": wrong_key}, method="GET")
        urllib.request.urlopen(req, timeout=20)
        item.update({"ok": False, "stage": "done", "message": "wrong key unexpectedly accepted"})
    except urllib.error.HTTPError as exc:
        item.update({"ok": exc.code == 403, "stage": "http_error", "http_status": exc.code, "preview": exc.read().decode("utf-8", "replace")[:500]})
    except Exception as exc:
        item.update({"ok": False, "stage": "exception", "error": type(exc).__name__, "message": str(exc)})
    api_key = original_key
    update("finished_auth_rejects_wrong_key")
    update("complete")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Incremental HTTP smoke test for GPT-API production/backends")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--repo-path", default=DEFAULT_REPO)
    parser.add_argument("--env-file", default="/root/GPT-API/.env")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--run-id", default=f"http_smoke_{int(time.time())}")
    parser.add_argument("--report", default="/tmp/gpt-api-http-smoke-report.json")
    parser.add_argument("--skip-phase13-job", action="store_true")
    args = parser.parse_args()
    api_key = args.api_key if args.api_key is not None else _load_key(Path(args.env_file))
    report = run_http_smoke(base_url=args.base_url, repo_path=args.repo_path, api_key=api_key, report_path=Path(args.report), run_id=args.run_id, include_phase13_job=not args.skip_phase13_job)
    print(json.dumps({"report": args.report, "stage": report.get("stage"), "total": report.get("total"), "passed": report.get("passed"), "failed": report.get("failed")}, indent=2))
    return 0 if report.get("failed") == 0 and report.get("stage") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())

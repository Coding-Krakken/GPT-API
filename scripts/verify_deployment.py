#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path(os.getenv("DEPLOY_VERIFY_OUTPUT_DIR", "/tmp/gpt-api-deployment-reports"))
PUBLIC_BASE_URL = "https://unscrutinized-immotile-jermaine.ngrok-free.dev"
TEST_KEY = "deploy-verify-test-key"
REQUIRED_CORE_ACTION_PATHS = {
    "/agent/coding-task",
    "/agent/coding-task/next",
    "/agent/coding-task/submit",
    "/agent/coding-task/finalize",
    "/repo/instructions",
    "/repo/overview",
    "/repo/preflight",
    "/env/discover",
    "/env/doctor",
    "/env/prepare-dry-run",
}
REQUIRED_FULL_CODING_ACTION_PATHS = REQUIRED_CORE_ACTION_PATHS | {
    "/coding/action",
    "/coding/repo/action",
    "/coding/env/action",
    "/coding/test/action",
    "/coding/quality/action",
}
REQUIRED_LIVE_GET_PATHS = [
    "/health",
    "/healthz",
    "/api/health",
    "/metrics",
    "/openapi.yaml",
    "/coding-openapi.yaml",
    "/coding-gpt-core-openapi.yaml",
]


@dataclass
class CheckResult:
    name: str
    status: str
    severity: str
    summary: str
    detail: Any = None


class VerificationError(Exception):
    pass


def redact(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:3]}...[REDACTED]...{value[-3:]}"


def run_git(args: list[str], timeout: int = 20) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def add_check(checks: list[CheckResult], name: str, ok: bool, summary: str, *, severity: str = "high", detail: Any = None) -> None:
    checks.append(CheckResult(name=name, status="passed" if ok else "failed", severity=severity, summary=summary, detail=detail))


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise VerificationError(f"{path.name} did not parse to an object")
    return data


def validate_schema_file(schema_path: Path, *, required_paths: set[str] | None = None) -> tuple[bool, str, dict[str, Any]]:
    try:
        data = load_yaml(schema_path)
    except Exception as exc:
        return False, f"schema parse failed: {exc}", {}
    paths = data.get("paths") or {}
    long_descriptions: list[dict[str, Any]] = []
    bare_objects: list[dict[str, Any]] = []
    missing_paths = sorted((required_paths or set()) - set(paths))
    bad_servers = []
    for server in data.get("servers", []) or []:
        url = str((server or {}).get("url", ""))
        if not url or url.endswith("/"):
            bad_servers.append(url)
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if not isinstance(op, dict):
                continue
            desc = op.get("description") or ""
            if len(desc) > 300:
                long_descriptions.append({"path": path, "method": method, "length": len(desc)})
            for status, response in (op.get("responses") or {}).items():
                schema = ((((response or {}).get("content") or {}).get("application/json") or {}).get("schema"))
                if schema == {"type": "object"}:
                    bare_objects.append({"path": path, "method": method, "status": status})
    ok = not missing_paths and not bad_servers and not long_descriptions and not bare_objects
    detail = {
        "path_count": len(paths),
        "missing_paths": missing_paths,
        "bad_servers": bad_servers,
        "long_descriptions": long_descriptions,
        "bare_object_schemas": bare_objects,
    }
    if ok:
        return True, f"{schema_path.name} validated path_count={len(paths)}", detail
    return False, f"{schema_path.name} failed deployment schema checks", detail


def verify_repo_state(checks: list[CheckResult], *, expect_commit: str | None, allow_dirty: bool) -> dict[str, Any]:
    code, head, err = run_git(["rev-parse", "HEAD"])
    add_check(checks, "git_head_available", code == 0, head if code == 0 else err, severity="critical")
    code, branch, err = run_git(["branch", "--show-current"])
    add_check(checks, "git_branch_available", code == 0 and bool(branch), branch or err, severity="medium")
    code, status, err = run_git(["status", "--short"])
    clean = code == 0 and not status
    add_check(checks, "git_worktree_clean", clean or allow_dirty, "clean" if clean else status or err, severity="high")
    if expect_commit:
        add_check(checks, "expected_commit_matches_head", head.startswith(expect_commit), f"head={head} expected={expect_commit}", severity="critical")
    code, origin_main, err = run_git(["rev-parse", "origin/main"])
    add_check(checks, "origin_main_available", code == 0, origin_main if code == 0 else err, severity="medium")
    if code == 0 and head:
        add_check(checks, "head_contains_origin_main", head == origin_main or bool(subprocess.run(["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"], cwd=ROOT).returncode == 0), f"head={head} origin/main={origin_main}", severity="medium")
    return {"head": head, "branch": branch, "clean": clean}


def verify_static_schemas(checks: list[CheckResult]) -> None:
    schema_specs = {
        "openapi.yaml": None,
        "cos-openapi.yaml": None,
        "coding-openapi.yaml": REQUIRED_FULL_CODING_ACTION_PATHS,
        "coding-gpt-core-openapi.yaml": REQUIRED_CORE_ACTION_PATHS,
    }
    for filename, required_paths in schema_specs.items():
        ok, summary, detail = validate_schema_file(ROOT / filename, required_paths=required_paths)
        add_check(checks, f"schema_{filename}", ok, summary, severity="critical" if filename.startswith("coding") else "high", detail=detail)


class InProcessClient:
    def __init__(self, api_key: str) -> None:
        os.environ.setdefault("API_KEY", api_key)
        os.environ.setdefault("OPERATOR_GPT_API_KEY", api_key)
        os.environ.setdefault("CODING_GPT_API_KEY", api_key)
        sys.path.insert(0, str(ROOT))
        from fastapi.testclient import TestClient
        from main import app

        self.client = TestClient(app)
        self.api_key = api_key
        self.base_url = "in-process"

    def get(self, path: str, *, auth: bool = False) -> tuple[int, str, dict[str, str]]:
        headers = {"x-api-key": self.api_key} if auth else {}
        response = self.client.get(path, headers=headers, follow_redirects=False)
        return response.status_code, response.text, dict(response.headers)

    def post(self, path: str, *, auth: bool = False, payload: dict[str, Any] | None = None) -> tuple[int, str, dict[str, str]]:
        headers = {"content-type": "application/json"}
        if auth:
            headers["x-api-key"] = self.api_key
        response = self.client.post(path, headers=headers, json=payload or {}, follow_redirects=False)
        return response.status_code, response.text, dict(response.headers)


class HttpClient:
    def __init__(self, base_url: str, api_key: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(self, method: str, path: str, *, auth: bool = False, body: bytes | None = None) -> tuple[int, str, dict[str, str]]:
        headers = {"content-type": "application/json", "ngrok-skip-browser-warning": "true"}
        if auth:
            headers["x-api-key"] = self.api_key
        req = urllib_request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urllib_request.urlopen(req, timeout=self.timeout) as response:
                return response.status, response.read().decode("utf-8", errors="replace"), dict(response.headers)
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace"), dict(exc.headers)
        except URLError as exc:
            raise VerificationError(f"{method} {path} failed: {exc}") from exc

    def get(self, path: str, *, auth: bool = False) -> tuple[int, str, dict[str, str]]:
        return self.request("GET", path, auth=auth)

    def post(self, path: str, *, auth: bool = False, payload: dict[str, Any] | None = None) -> tuple[int, str, dict[str, str]]:
        return self.request("POST", path, auth=auth, body=json.dumps(payload or {}).encode("utf-8"))


def parse_yaml_text(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise VerificationError("served YAML was not an object")
    return data


def verify_service(client: Any, checks: list[CheckResult], *, label: str, require_commit: str | None = None) -> None:
    for path in ["/health", "/healthz", "/api/health"]:
        try:
            status, body, _ = client.get(path)
            ok = status == 200 and '"status"' in body and "ok" in body
            add_check(checks, f"{label}_{path}_healthy", ok, f"HTTP {status}", severity="critical", detail=body[:500])
        except Exception as exc:
            add_check(checks, f"{label}_{path}_healthy", False, str(exc), severity="critical")
    try:
        status, body, _ = client.get("/metrics")
        add_check(checks, f"{label}_metrics_available", status == 200 and "top_endpoints" in body, f"HTTP {status}", severity="high", detail=body[:800])
    except Exception as exc:
        add_check(checks, f"{label}_metrics_available", False, str(exc), severity="high")
    for schema_path, required_paths in [
        ("/openapi.yaml", None),
        ("/coding-openapi.yaml", REQUIRED_FULL_CODING_ACTION_PATHS),
        ("/coding-gpt-core-openapi.yaml", REQUIRED_CORE_ACTION_PATHS),
    ]:
        try:
            status, body, _ = client.get(schema_path)
            if status != 200:
                add_check(checks, f"{label}_{schema_path}_served", False, f"HTTP {status}", severity="critical", detail=body[:800])
                continue
            data = parse_yaml_text(body)
            paths = set((data.get("paths") or {}).keys())
            missing = sorted((required_paths or set()) - paths)
            bad_servers = [str((s or {}).get("url", "")) for s in data.get("servers", []) or [] if not str((s or {}).get("url", "")) or str((s or {}).get("url", "")).endswith("/")]
            ok = not missing and not bad_servers
            add_check(checks, f"{label}_{schema_path}_served", ok, f"HTTP {status} path_count={len(paths)}", severity="critical", detail={"missing_paths": missing, "bad_servers": bad_servers})
        except Exception as exc:
            add_check(checks, f"{label}_{schema_path}_served", False, str(exc), severity="critical")
    for path in ["/agent/coding-task", "/repo/instructions", "/env/discover", "/coding/env/action"]:
        try:
            status, body, _ = client.post(path, auth=True)
            add_check(checks, f"{label}_{path}_route_present", status != 404, f"HTTP {status}", severity="critical", detail=body[:800])
        except Exception as exc:
            add_check(checks, f"{label}_{path}_route_present", False, str(exc), severity="critical")
    if require_commit:
        try:
            status, body, _ = client.get("/diagnostics/summary", auth=True)
            ok = status == 200 and require_commit in body
            add_check(checks, f"{label}_diagnostics_commit_matches", ok, f"HTTP {status} expected_commit={require_commit}", severity="high", detail=body[:1200])
        except Exception as exc:
            add_check(checks, f"{label}_diagnostics_commit_matches", False, str(exc), severity="high")


def write_reports(checks: list[CheckResult], metadata: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    report = {
        "status": "passed" if all(c.status == "passed" for c in checks) else "failed",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metadata": metadata,
        "checks": [asdict(c) for c in checks],
        "summary": {
            "total": len(checks),
            "passed": sum(1 for c in checks if c.status == "passed"),
            "failed": sum(1 for c in checks if c.status == "failed"),
            "critical_failed": sum(1 for c in checks if c.status == "failed" and c.severity == "critical"),
        },
    }
    json_path = output_dir / f"deployment_verification_{stamp}.json"
    md_path = output_dir / f"deployment_verification_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Deployment Verification Report",
        "",
        f"Generated: {report['generated_at']}",
        f"Status: **{report['status']}**",
        "",
        "## Summary",
        "",
        f"- Total checks: {report['summary']['total']}",
        f"- Passed: {report['summary']['passed']}",
        f"- Failed: {report['summary']['failed']}",
        f"- Critical failed: {report['summary']['critical_failed']}",
        "",
        "## Metadata",
        "",
    ]
    for key, value in metadata.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", "", "| Status | Severity | Check | Summary |", "|---|---|---|---|"])
    for check in checks:
        summary = str(check.summary).replace("|", "/")[:220]
        lines.append(f"| {check.status} | {check.severity} | `{check.name}` | {summary} |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify GPT-API deployment readiness and live Action schema availability.")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"), help="Live service base URL for --live checks.")
    parser.add_argument("--public-url", default=os.getenv("PUBLIC_BASE_URL", PUBLIC_BASE_URL), help="Public tunnel URL used for optional --public checks.")
    parser.add_argument("--api-key", default=os.getenv("API_KEY", TEST_KEY), help="API key for authenticated verification calls.")
    parser.add_argument("--expect-commit", default=os.getenv("EXPECT_COMMIT", ""), help="Expected git commit prefix for local/live diagnostics checks.")
    parser.add_argument("--live", action="store_true", help="Run checks against --base-url instead of only in-process checks.")
    parser.add_argument("--public", action="store_true", help="Also check --public-url, typically the ngrok URL.")
    parser.add_argument("--require-live", action="store_true", help="Fail if live/public URLs are not checked.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow a dirty local worktree for in-progress verification.")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP timeout in seconds.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for JSON and Markdown reports.")
    args = parser.parse_args(argv)

    checks: list[CheckResult] = []
    repo_meta = verify_repo_state(checks, expect_commit=args.expect_commit or None, allow_dirty=args.allow_dirty)
    verify_static_schemas(checks)
    api_key = args.api_key or TEST_KEY
    metadata = {
        "branch": repo_meta.get("branch", ""),
        "head": repo_meta.get("head", ""),
        "clean": repo_meta.get("clean", False),
        "base_url": args.base_url,
        "public_url": args.public_url if args.public else "not_checked",
        "api_key": redact(api_key),
        "mode": "live" if args.live else "in-process",
    }

    if args.live:
        try:
            verify_service(HttpClient(args.base_url, api_key, args.timeout), checks, label="live", require_commit=args.expect_commit or None)
        except Exception as exc:
            add_check(checks, "live_service_unhandled_error", False, str(exc), severity="critical")
    else:
        verify_service(InProcessClient(api_key), checks, label="in_process", require_commit=None)
    if args.public:
        try:
            verify_service(HttpClient(args.public_url, api_key, args.timeout), checks, label="public", require_commit=args.expect_commit or None)
        except Exception as exc:
            add_check(checks, "public_service_unhandled_error", False, str(exc), severity="critical")
    if args.require_live and not (args.live or args.public):
        add_check(checks, "live_verification_required", False, "--require-live was set without --live or --public", severity="critical")

    report_paths = write_reports(checks, metadata, Path(args.output_dir))
    failed = [check for check in checks if check.status == "failed"]
    for check in checks:
        prefix = "ok" if check.status == "passed" else "not ok"
        print(f"{prefix} {check.name}: {check.summary}")
    print(json.dumps({"status": "passed" if not failed else "failed", "failed": len(failed), "reports": report_paths}, indent=2))
    return 1 if failed else 0


def main() -> int:
    return run(None)


def main_args_for_tests(argv: list[str]) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())

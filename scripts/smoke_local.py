#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEST_KEY = "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d"


class SmokeFailure(Exception):
    pass


def _json_headers(api_key: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


class InProcessClient:
    def __init__(self) -> None:
        os.environ.setdefault("API_KEY", TEST_KEY)
        os.environ.setdefault("OPERATOR_GPT_API_KEY", TEST_KEY)
        os.environ.setdefault("CODING_GPT_API_KEY", TEST_KEY)
        sys.path.insert(0, str(ROOT))
        from fastapi.testclient import TestClient
        from main import app

        self.client = TestClient(app)
        self.api_key = TEST_KEY

    def _testclient_url(self, path: str) -> str:
        return f"http://testserver{path}" if path.startswith("//") else path

    def get(self, path: str, *, auth: bool = False) -> tuple[int, str, dict[str, str]]:
        headers = {"x-api-key": self.api_key} if auth else {}
        response = self.client.get(self._testclient_url(path), headers=headers, follow_redirects=False)
        return response.status_code, response.text, dict(response.headers)

    def post(self, path: str, *, payload: dict[str, Any] | None = None, auth: bool = False) -> tuple[int, str, dict[str, str]]:
        response = self.client.post(
            self._testclient_url(path),
            headers=_json_headers(self.api_key if auth else None),
            json=payload or {},
            follow_redirects=False,
        )
        return response.status_code, response.text, dict(response.headers)


class LiveClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _request(self, method: str, path: str, *, auth: bool = False, body: bytes | None = None) -> tuple[int, str, dict[str, str]]:
        headers = _json_headers(self.api_key if auth else None)
        req = urllib_request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urllib_request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode("utf-8", errors="replace"), dict(resp.headers)
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace"), dict(exc.headers)
        except URLError as exc:
            raise SmokeFailure(f"live request failed for {method} {path}: {exc}") from exc

    def get(self, path: str, *, auth: bool = False) -> tuple[int, str, dict[str, str]]:
        return self._request("GET", path, auth=auth)

    def post(self, path: str, *, payload: dict[str, Any] | None = None, auth: bool = False) -> tuple[int, str, dict[str, str]]:
        return self._request("POST", path, auth=auth, body=json.dumps(payload or {}).encode("utf-8"))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def assert_status(label: str, actual: int, allowed: set[int]) -> None:
    check(actual in allowed, f"{label}: expected one of {sorted(allowed)}, got {actual}")


def validate_served_openapi(text: str) -> None:
    data = yaml.safe_load(text)
    check(isinstance(data, dict), "served openapi.yaml did not parse as an object")
    check("paths" in data and data["paths"], "served openapi.yaml has no paths")
    for server in data.get("servers", []) or []:
        url = str(server.get("url", ""))
        check(url and not url.endswith("/"), f"server URL must be non-empty and slashless: {url!r}")


def _has_redirect_location(headers: dict[str, str]) -> bool:
    return any(key.lower() == "location" for key in headers)


def run_matrix(client: InProcessClient | LiveClient) -> list[str]:
    passed: list[str] = []

    for path in ["/health", "/healthz", "/api/health"]:
        status, body, _ = client.get(path)
        assert_status(path, status, {200})
        check('"status"' in body and "ok" in body, f"{path}: body does not look healthy")
        passed.append(path)

    status, body, _ = client.get("/openapi.yaml")
    assert_status("/openapi.yaml", status, {200})
    validate_served_openapi(body)
    passed.append("/openapi.yaml")

    status, _, _ = client.get("/metrics")
    assert_status("/metrics without auth", status, {403})
    status, _, _ = client.get("/metrics", auth=True)
    assert_status("/metrics with auth", status, {200})
    passed.append("/metrics")

    for path in ["/shell", "/files", "/git", "/monitor", "/dispatch", "/package"]:
        status, _, headers = client.post(path, auth=False)
        check(status != 307, f"{path}: must not redirect")
        check(not _has_redirect_location(headers), f"{path}: unexpected redirect location")
        assert_status(f"{path} auth guard", status, {403})
        passed.append(f"{path} no-redirect")

    for path in ["//agent/coding-task", "/agent//coding-task", "//repo/instructions"]:
        status, _, _ = client.post(path, auth=True)
        check(status != 404, f"{path}: duplicate slash should not be 404")
        assert_status(f"{path} duplicate-slash", status, {400, 422})
        passed.append(f"{path} normalized")

    for path in ["/repo/overview", "/repo/instructions", "/agent/coding-task", "/coding/repo/action"]:
        status, _, _ = client.post(path, auth=True)
        check(status != 404, f"{path}: documented typed coding endpoint missing")
        assert_status(f"{path} typed endpoint", status, {200, 400, 422})
        passed.append(path)

    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 22 GPT-API smoke verification matrix.")
    parser.add_argument("--live", action="store_true", help="Run against BASE_URL instead of the in-process FastAPI app.")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY", TEST_KEY))
    args = parser.parse_args()

    try:
        client: InProcessClient | LiveClient
        client = LiveClient(args.base_url, args.api_key) if args.live else InProcessClient()
        passed = run_matrix(client)
    except SmokeFailure as exc:
        print(f"smoke verification failed: {exc}", file=sys.stderr)
        return 1

    for item in passed:
        print(f"ok {item}")
    print(f"smoke verification passed checks={len(passed)} mode={'live' if args.live else 'in-process'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

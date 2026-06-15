#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_FILES = [
    "openapi.yaml",
    "cos-openapi.yaml",
    "coding-openapi.yaml",
    "coding-gpt-core-openapi.yaml",
]


class ValidationFailure(Exception):
    pass


def load_schema(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationFailure(f"{path.name}: failed to parse YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationFailure(f"{path.name}: schema root is not an object")
    return data


def validate_basic_shape(name: str, data: dict[str, Any]) -> None:
    if not str(data.get("openapi", "")).startswith("3."):
        raise ValidationFailure(f"{name}: missing or unsupported openapi version")
    if not isinstance(data.get("info"), dict):
        raise ValidationFailure(f"{name}: missing info object")
    if not isinstance(data.get("paths"), dict) or not data["paths"]:
        raise ValidationFailure(f"{name}: missing non-empty paths object")


def validate_server_urls(name: str, data: dict[str, Any]) -> None:
    for server in data.get("servers", []) or []:
        if not isinstance(server, dict):
            raise ValidationFailure(f"{name}: server entry is not an object")
        url = str(server.get("url", ""))
        if not url:
            raise ValidationFailure(f"{name}: server entry missing url")
        if url.endswith("/"):
            raise ValidationFailure(f"{name}: server url must not end with '/': {url}")


def validate_operation_ids(name: str, data: dict[str, Any]) -> None:
    seen: dict[str, str] = {}
    for path, item in (data.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}:
                continue
            if not isinstance(operation, dict):
                raise ValidationFailure(f"{name}: {method.upper()} {path} operation is not an object")
            op_id = operation.get("operationId")
            if not op_id:
                continue
            if op_id in seen:
                raise ValidationFailure(f"{name}: duplicate operationId {op_id!r} at {method.upper()} {path} and {seen[op_id]}")
            seen[op_id] = f"{method.upper()} {path}"


def validate_security(name: str, data: dict[str, Any]) -> None:
    security_schemes = (((data.get("components") or {}).get("securitySchemes") or {}))
    if "ApiKeyAuth" not in security_schemes:
        raise ValidationFailure(f"{name}: missing components.securitySchemes.ApiKeyAuth")
    scheme = security_schemes["ApiKeyAuth"]
    if scheme.get("type") != "apiKey" or scheme.get("in") != "header" or scheme.get("name") != "x-api-key":
        raise ValidationFailure(f"{name}: ApiKeyAuth must be apiKey header x-api-key")


def validate_semantic_if_available(name: str, data: dict[str, Any]) -> str:
    try:
        from openapi_spec_validator import validate  # type: ignore
    except Exception:
        return "semantic_validator_unavailable"
    try:
        validate(data)
    except Exception as exc:
        raise ValidationFailure(f"{name}: semantic OpenAPI validation failed: {exc}") from exc
    return "semantic_validation_passed"


def live_route_methods() -> set[tuple[str, str]]:
    sys.path.insert(0, str(ROOT))
    from main import app  # noqa: WPS433

    out: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        for method in getattr(route, "methods", []) or []:
            if method in {"HEAD", "OPTIONS"}:
                continue
            out.add((path, method.upper()))
    return out


def validate_paths_match_live_routes(name: str, data: dict[str, Any], live: set[tuple[str, str]]) -> None:
    missing: list[str] = []
    for path, item in (data.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in item:
            method_upper = method.upper()
            if method.lower() not in {"get", "put", "post", "delete", "patch"}:
                continue
            if (path, method_upper) not in live:
                missing.append(f"{method_upper} {path}")
    if missing:
        preview = ", ".join(missing[:20])
        more = "" if len(missing) <= 20 else f" ... and {len(missing) - 20} more"
        raise ValidationFailure(f"{name}: schema paths not implemented by FastAPI: {preview}{more}")


def validate_file(path: Path, live: set[tuple[str, str]] | None, check_live_routes: bool) -> dict[str, Any]:
    data = load_schema(path)
    validate_basic_shape(path.name, data)
    validate_server_urls(path.name, data)
    validate_operation_ids(path.name, data)
    validate_security(path.name, data)
    semantic = validate_semantic_if_available(path.name, data)
    if check_live_routes and live is not None:
        validate_paths_match_live_routes(path.name, data, live)
    return {"file": path.name, "paths": len(data.get("paths", {})), "semantic": semantic}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GPT-API OpenAPI YAML files.")
    parser.add_argument("files", nargs="*", default=DEFAULT_SCHEMA_FILES)
    parser.add_argument("--check-live-routes", action="store_true", help="Require each schema path/method to exist in FastAPI.")
    args = parser.parse_args()

    live = live_route_methods() if args.check_live_routes else None
    summaries = []
    try:
        for rel in args.files:
            path = (ROOT / rel).resolve()
            summaries.append(validate_file(path, live, args.check_live_routes))
    except ValidationFailure as exc:
        print(f"openapi validation failed: {exc}", file=sys.stderr)
        return 1
    for summary in summaries:
        print(f"{summary['file']}: ok paths={summary['paths']} {summary['semantic']}")
    print("openapi validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

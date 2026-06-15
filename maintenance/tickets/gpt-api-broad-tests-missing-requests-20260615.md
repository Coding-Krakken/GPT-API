# Maintainer Ticket: Broad endpoint test collection blocked by missing requests

## Issue
While running broader endpoint tests after the phase 1-22 suites passed, pytest failed collecting `tests/test_api.py` because the `requests` package is missing from the active environment/dependencies.

## Command

```bash
cd /root/GPT-API
pytest -q tests/test_api.py tests/test_shell.py tests/test_files.py tests/test_code.py tests/test_system.py tests/test_monitor.py tests/test_git.py tests/test_package.py tests/test_batch.py tests/test_refactor.py tests/test_apps.py tests/test_coding_routes.py tests/test_coding_openapi_scope.py tests/test_coding_safety_boundaries.py tests/test_coding_workflow_guards.py tests/test_expanded_endpoint_contract.py
```

## Error

```text
ModuleNotFoundError: No module named 'requests'
```

## Next action
Add `requests` to project dependencies or refactor the legacy test to use existing FastAPI TestClient/httpx fixtures.

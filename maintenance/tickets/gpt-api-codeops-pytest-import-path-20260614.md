---
id: "gpt-api-codeops-pytest-import-path-20260614"
status: "resolved"
severity: "high"
area: "codeops"
created: "2026-06-15"
resolved_at: "2026-06-15"
resolved_by_commit: "8dd867b"
verification_command: "pytest -q tests/test_code_phase2.py tests/test_code.py tests/test_code_api_hardening.py tests/test_code_content_edge_cases.py tests/test_expanded_endpoint_contract.py tests/test_phase15_release_gate.py"
verification_result: "50 passed, 1 warning"
resolution_summary: "Phase 2 implemented robust /code test mode: language inference, repo-root pytest, working_dir PYTHONPATH, multi-file argv/selectors, and validationResult output."
---

# Maintainer Ticket: codeOps test runner failed to import repo main module

## Issue
While testing `/root/GPT-API/tests/test_phase4_phase7_contract.py`, the `codeOps` endpoint with `action=test`, `path=/root/GPT-API/tests/test_phase4_phase7_contract.py`, and `working_dir=/root/GPT-API` failed before test collection with `ModuleNotFoundError: No module named 'main'`.

## Attempted action
```json
{
  "action": "test",
  "path": "/root/GPT-API/tests/test_phase4_phase7_contract.py",
  "language": "python",
  "working_dir": "/root/GPT-API",
  "timeout_seconds": 120
}
```

## Error
```text
ImportError while loading conftest '/root/GPT-API/tests/conftest.py'.
tests/conftest.py:6: in <module>
    from main import app
E   ModuleNotFoundError: No module named 'main'
```

## Context
The repository's `tests/conftest.py` imports `main` before it mutates `sys.path`, so the process must be launched with the repository root on `PYTHONPATH` or from the repo root in a way that pytest includes it. The direct shell command `cd /root/GPT-API && python -m pytest ...` is the current workaround.

## Workaround
Use shell:
```bash
cd /root/GPT-API && python -m pytest -q tests/test_phase4_phase7_contract.py
```


## Phase 2 resolution

Implemented and verified in Phase 2. `/code` test mode now supports inferred Python language for pytest files and repo roots, repository-root pytest execution, safe multi-file pytest selectors through `argv` or `args`, `PYTHONPATH` injection from `working_dir`, and structured `validationResult` metadata for test runs.

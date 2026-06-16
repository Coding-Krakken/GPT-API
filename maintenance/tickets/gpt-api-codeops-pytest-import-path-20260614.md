---
id: "gpt-api-codeops-pytest-import-path-20260614"
status: "open"
severity: "high"
area: "codeops"
created: "2026-06-15"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Add /code regression tests for inferred language, repo-root pytest, PYTHONPATH, and argv selectors."
verification_result: "not_run"
resolution_summary: "codeOps test-mode robustness remains actionable and should be fixed in Phase 2."
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

---
id: gpt-api-tests-missing-requests-dependency-20260614
status: open
severity: high
area: maintenance
created: 2026-06-15
resolved:
---

# Maintainer Ticket: pytest tests collection blocked by missing requests dependency

## Issue
Running the `tests/` suite failed during collection because three test modules import `requests`, which is not installed in `/root/GPT-API/.venv`.

## Command
```bash
cd /root/GPT-API && .venv/bin/python -m pytest -q tests
```

## Errors
```text
tests/comprehensive_test.py:1: ModuleNotFoundError: No module named 'requests'
tests/test_api.py:1: ModuleNotFoundError: No module named 'requests'
tests/test_full_api.py:2: ModuleNotFoundError: No module named 'requests'
```

## Suggested fix
Either add `requests` to the test requirements or mark these legacy/live HTTP tests separately from the in-process FastAPI test suite.

## Workaround
Run the maintained in-process tests while excluding the three requests-based modules.

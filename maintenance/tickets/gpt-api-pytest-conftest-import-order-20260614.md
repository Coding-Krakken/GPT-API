---
id: "gpt-api-pytest-conftest-import-order-20260614"
status: "resolved"
severity: "medium"
area: "environment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified full pytest passes from repository root."
---

# GPT-API pytest conftest import order blocks tests

## Issue
Running a focused pytest file from `/root/GPT-API` failed while loading `tests/conftest.py` because `from main import app` runs before the repository root is inserted into `sys.path`.

## Command
```bash
pytest tests/test_phase8_phase10_hardening.py
```

## Error
```text
ImportError while loading conftest '/root/GPT-API/tests/conftest.py'.
tests/conftest.py:6: in <module>
    from main import app
E   ModuleNotFoundError: No module named 'main'
```

## Root cause
`tests/conftest.py` imports `main` before executing:

```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

## Fix
Move the `sys.path.insert(...)` before `from main import app`.

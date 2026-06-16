---
id: "gpt-api-full-pytest-manual-script-collected-20260615"
status: "resolved"
severity: "medium"
area: "environment"
created: "2026-06-16"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified pytest is constrained to tests/ and full suite passes."
---

# Maintainer Ticket: Full pytest collected manual smoke script and exited

## Issue
Running full `pytest -q` collected `manual_elevate_smoke_endpoint_test.py`, which executes top-level code and raises `SystemExit` during collection.

## Command

```bash
cd /root/GPT-API
pytest -q
```

## Error

```text
File "/root/GPT-API/manual_elevate_smoke_endpoint_test.py", line 15, in <module>
raise SystemExit(...)
SystemExit: 0
```

## Next action
Constrain pytest collection to real test modules, excluding root-level `manual_*.py` smoke scripts.

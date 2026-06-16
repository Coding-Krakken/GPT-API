---
id: "gpt-api-full-pytest-manual-script-systemexit-20260614"
status: "resolved"
severity: "medium"
area: "environment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified pytest is constrained to tests/ and full suite passes."
---

# Maintainer Ticket: Full pytest collects manual smoke script and exits during import

## Issue
Running full repository pytest from `/root/GPT-API` failed during collection because `manual_elevate_smoke_endpoint_test.py` executes code at import time and raises `SystemExit`.

## Command
```bash
cd /root/GPT-API && .venv/bin/python -m pytest -q
```

## Error summary
```text
File "/root/GPT-API/manual_elevate_smoke_endpoint_test.py", line 15, in <module>
    raise SystemExit(...)
SystemExit: 0
mainloop: caught unexpected SystemExit!
```

## Context
The script printed a successful smoke report before exiting, but pytest treats import-time `SystemExit` as an internal collection error.

## Suggested fix
Move manual smoke scripts out of pytest discovery scope, rename them so they are not collected, or guard executable code with:

```python
if __name__ == "__main__":
    ...
```

## Workaround
Run the real test suite with:

```bash
.venv/bin/python -m pytest -q tests
```

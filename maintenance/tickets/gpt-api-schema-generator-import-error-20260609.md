---
id: "gpt-api-schema-generator-import-error-20260609"
status: "resolved"
severity: "medium"
area: "schema"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified scripts/validate_openapi.py passes on all schemas."
---

# Schema generator import error

## Issue
The schema generator was written to `/tmp/gen_coding_schemas.py` and run from `/root/GPT-API`, but Python used `/tmp` as `sys.path[0]`, so it could not import the repo's `main.py`.

## Error
```text
ModuleNotFoundError: No module named 'main'
```

## Command
```bash
cd /root/GPT-API && python /tmp/gen_coding_schemas.py
```

## Fix
Run with `PYTHONPATH=/root/GPT-API` or add the repo root to `sys.path` inside the script.

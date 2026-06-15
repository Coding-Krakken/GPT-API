---
id: gpt-api-schema-generator-import-error-20260609
status: open
severity: medium
area: schema
created: 2026-06-15
resolved:
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

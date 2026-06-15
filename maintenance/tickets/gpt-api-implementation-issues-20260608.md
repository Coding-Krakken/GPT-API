---
id: gpt-api-implementation-issues-20260608
status: open
severity: low
area: schema
created: 2026-06-15
resolved:
---

# GPT-API implementation issue log

## Context
During implementation of the safe Coding GPT branch `feature/coding-gpt-safe-agent`, two environment/project issues were encountered while attempting validation.

## Issue 1: pytest missing from active Python environment

### Attempted command
```bash
cd /root/GPT-API && python -m pytest tests/test_coding_openapi_scope.py tests/test_coding_routes.py -q
```

### Output
```text
/root/GPT-API/.venv/bin/python: No module named pytest
```

### Impact
Could not run tests until test dependencies are installed in the active environment.

## Issue 2: requirements.txt could not be read by structured file endpoint

### Attempted action
`manageFiles` read of `/root/GPT-API/requirements.txt`

### Output
```json
{
  "error": {
    "code": "internal_error",
    "message": "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte"
  },
  "status": 500
}
```

### Impact
The requirements file appears to be non-UTF-8 encoded or has invalid leading bytes, preventing direct structured UTF-8 read.

## Branch
`feature/coding-gpt-safe-agent`

## Next action
Use shell tools to inspect the file encoding and install or invoke test dependencies safely, then rerun validation.

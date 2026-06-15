---
id: gpt-api-phase13-patch-command-too-long-20260610
status: open
severity: medium
area: endpoint
created: 2026-06-15
resolved:
---

# Phase 13 endpoint patch command exceeded shell API length

## Issue
While patching `routes/evals.py` to make `/evals/phase13/run` non-blocking/job-based, the inline shell command exceeded the control API maximum command length.

## Error
```json
{
  "code": "command_too_long",
  "message": "Command exceeds maximum allowed length (4096 characters)."
}
```

## Impact
No repository files were modified by the failed oversized command.

## Next step
Write a temporary patch script file under `/tmp` and execute that smaller script from the shell API.

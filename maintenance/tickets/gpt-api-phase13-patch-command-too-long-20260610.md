---
id: "gpt-api-phase13-patch-command-too-long-20260610"
status: "obsolete"
severity: "low"
area: "patch-safety"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
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

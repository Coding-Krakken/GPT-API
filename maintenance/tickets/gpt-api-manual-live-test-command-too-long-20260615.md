---
id: "gpt-api-manual-live-test-command-too-long-20260615"
status: "obsolete"
severity: "low"
area: "deployment"
created: "2026-06-16"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Maintainer Ticket: Manual live endpoint test command exceeded shell length

## Issue
While manually testing the separate backend instance on port 18088, the combined shell/Python command for all affected endpoint checks exceeded the `/shell` 4096-character command limit.

## Attempted work
Manual live checks for:
- health and auth behavior
- no-redirect action endpoints
- duplicate-slash normalization
- dangerous-operation confirmation guards
- shell background lifecycle
- file delete confirmation
- package dry-run confirmation
- apps validation after confirmation
- blocked `.env` patch preview
- batch rollback confirmation

## Error

```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."},"status":400}
```

## Workaround
Write the manual test script to a temp file and execute the file.

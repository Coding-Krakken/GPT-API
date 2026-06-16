---
id: "gpt-api-schema-instruction-update-command-too-long-20260615"
status: "obsolete"
severity: "low"
area: "patch-safety"
created: "2026-06-16"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Maintainer Ticket: Schema/instruction update command exceeded shell length

## Issue
While updating OpenAPI schema and instruction files to reflect the current confirmation policy, health routes, and blocked patch behavior, the combined shell/Python edit command exceeded the `/shell` 4096-character command limit.

## Attempted work
- Add `confirm` and `confirmation` fields to affected OpenAPI request schemas.
- Add health endpoint docs to the main OpenAPI schema.
- Document `blocked_patch_path` behavior in the coding schema.
- Validate schemas after patching.

## Error

```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."},"status":400}
```

## Workaround
Write a short script file and execute it.

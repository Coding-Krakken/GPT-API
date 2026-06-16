---
id: "gpt-api-broad-hardening-command-too-long-20260615"
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

# Maintainer Ticket: Broad hardening patch command exceeded shell limit

## Issue
While updating legacy tests and patch safety behavior during the broad hardening pass, a combined Python edit command exceeded the `/shell` 4096-character command limit.

## Attempted work
- Make `utils/patching.preview` propagate `PolicyError` so blocked paths return status 400.
- Add explicit confirmation to legacy tests that intentionally exercise guarded operations.
- Align legacy refactor error assertions with the standardized error envelope.

## Error

```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."},"status":400}
```

## Workaround
Apply smaller file-scoped edits.

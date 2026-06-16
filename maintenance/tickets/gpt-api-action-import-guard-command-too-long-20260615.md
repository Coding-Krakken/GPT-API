---
id: "gpt-api-action-import-guard-command-too-long-20260615"
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

# Maintainer Ticket: Action import guard patch command exceeded shell limit

## Issue
While responding to repeated OpenAPI Action import errors, a combined schema/script patch command exceeded the `/shell` 4096-character limit.

## Intended changes
- Shorten the remaining long description in `cos-openapi.yaml`.
- Add properties to bare object response schemas for diagnostics endpoints in coding schemas.
- Extend `scripts/validate_openapi.py` with Action import constraints:
  - operation descriptions must be <= 300 chars
  - object response schemas must define `properties` or `additionalProperties: true`

## Error

```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."},"status":400}
```

## Workaround
Write a patch script file and run it instead of embedding the full script in the shell command.

---
id: "gpt-api-phase18-20-command-too-long-20260615"
status: "obsolete"
severity: "low"
area: "tooling"
created: "2026-06-16"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Maintainer Ticket: Phase 18-20 implementation blocked by shell command length

## Issue
While implementing Phases 18-20 in `/root/GPT-API`, a single shell command that attempted to create `config/policy.yaml` and `utils/operation_policy.py` exceeded the 4096-character `/shell` command limit.

## Attempted action
Create Phase 18 operation policy config and utility module with a heredoc through `/shell`.

## Error response
```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."},"status":400}
```

## Workaround
Use the structured `/files` endpoint for large file writes, then run smaller validation commands.

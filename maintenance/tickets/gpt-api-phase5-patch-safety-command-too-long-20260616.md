---
id: "gpt-api-phase5-patch-safety-command-too-long-20260616"
status: "resolved"
severity: "medium"
area: "tooling"
created: "2026-06-16"
resolved_at: "2026-06-16"
resolved_by_commit: "this-commit"
verification_command: "Use manageFiles/write for the Phase 5 patch script, then run a short shell command."
verification_result: "passed"
resolution_summary: "The oversized shell command was not executed; continuing with a file-backed script to avoid the shell command length limit."
---

# Maintainer Ticket: Phase 5 patch safety command exceeded shell length

## Issue
While implementing Phase 5 patch/file safety hardening, a single shell command attempted to create a long Python patch script and run validation. The shell endpoint rejected it because it exceeded the 4096-character command limit.

## Error
```json
{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."}
```

## Impact
No repository files were modified by the rejected command.

## Resolution
Use the file API to write the Python patch script to `/tmp`, then execute it with a short shell command.

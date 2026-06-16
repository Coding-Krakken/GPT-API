---
id: "gpt-api-phase18-20-git-helper-kwargs-20260615"
status: "open"
severity: "medium"
area: "tooling"
created: "2026-06-16"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Add tool contract tests or documentation for supported fields/branch creation."
verification_result: "not_run"
resolution_summary: "Structured tool contract mismatch remains actionable for operator tooling."
---

# Maintainer Ticket: gitControl rejected max_output_bytes parameter

## Issue
During Phase 18-20 commit preparation for `/root/GPT-API`, `gitControl` failed when called with `max_output_bytes`.

## Error
```text
UnrecognizedKwargsError: max_output_bytes
```

## Workaround
Use standard git shell commands for status, add, commit, and push.

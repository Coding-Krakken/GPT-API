---
id: "gpt-api-phase21-22-git-helper-kwargs-20260615"
status: "open"
severity: "medium"
area: "tooling"
created: "2026-06-15"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Add tool contract tests or documentation for supported fields/branch creation."
verification_result: "not_run"
resolution_summary: "Structured tool contract mismatch remains actionable for operator tooling."
---

# Maintainer Ticket: gitControl commit rejected unsupported max_output_bytes parameter

## Issue
While committing Phase 21/22 changes in `/root/GPT-API`, the structured git helper rejected an unsupported `max_output_bytes` argument.

## Attempted request

```json
{"action":"commit","path":"/root/GPT-API","message":"docs: add phase 21-22 verification runbook","timeout_seconds":120,"max_output_bytes":30000}
```

## Error

```text
UnrecognizedKwargsError: max_output_bytes
```

## Workaround
Retry `gitControl` commit without `max_output_bytes`.

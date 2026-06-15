---
id: gpt-api-phase21-22-git-helper-kwargs-20260615
status: open
severity: high
area: runtime
created: 2026-06-15
resolved:
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

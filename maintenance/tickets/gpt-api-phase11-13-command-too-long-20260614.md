---
id: gpt-api-phase11-13-command-too-long-20260614
status: open
severity: medium
area: endpoint
created: 2026-06-15
resolved:
---

# GPT-API Phase 11-13 implementation command exceeded shell length limit

## Issue
A shell command intended to create `utils/metrics.py`, patch `main.py`, and compile-check both files exceeded the `/shell` endpoint maximum command length.

## Error
```json
{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."}
```

## Context
Repository: `/root/GPT-API`
Task: implement Phase 11 metrics middleware and endpoints.

## Workaround
Use the file management endpoint to write files and smaller shell commands for validation.

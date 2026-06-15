---
id: gpt-api-phases8-10-command-too-long-20260614
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# GPT-API Phases 8-10 implementation blocked by shell command length

## Issue
While implementing Phases 8-10 in `/root/GPT-API`, an attempted multi-file patch via `/shell` exceeded the 4096 character command limit and returned `command_too_long`.

## Attempted action
A shell heredoc tried to rewrite `utils/audit.py` and patch `routes/shell.py`/`routes/code.py` in one call.

## Error
```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."},"status":400}
```

## Context
This is expected policy behavior and directly validates the need for Phase 9 improvements: use `/files`, `/code`, `/batch`, or a dedicated `/script/run` endpoint for large scripts instead of giant shell commands.

## Workaround
Continue using file-level writes and smaller patch commands.

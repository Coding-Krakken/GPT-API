---
id: gpt-api-phase1-command-too-long-20260609
status: open
severity: medium
area: endpoint
created: 2026-06-15
resolved:
---

# Phase 1 telemetry patch command too long

## Issue
While implementing Phase 1 telemetry, a shell command that patched `routes/coding_dispatch.py` exceeded the control API's 4096-character command limit.

## Error
```json
{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."}
```

## Intended action
Patch the Coding GPT dispatcher so every dispatcher call emits sanitized telemetry events:

- `dispatcher_called`
- `action_completed`
- `action_failed`
- `dispatcher_missing_payload`
- `dispatcher_retry_suggested`

## Resolution
Write the patch logic into a temporary Python script and execute it from the repo instead of embedding it in one large shell command.

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

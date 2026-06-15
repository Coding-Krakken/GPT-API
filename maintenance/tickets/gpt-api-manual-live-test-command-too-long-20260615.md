# Maintainer Ticket: Manual live endpoint test command exceeded shell length

## Issue
While manually testing the separate backend instance on port 18088, the combined shell/Python command for all affected endpoint checks exceeded the `/shell` 4096-character command limit.

## Attempted work
Manual live checks for:
- health and auth behavior
- no-redirect action endpoints
- duplicate-slash normalization
- dangerous-operation confirmation guards
- shell background lifecycle
- file delete confirmation
- package dry-run confirmation
- apps validation after confirmation
- blocked `.env` patch preview
- batch rollback confirmation

## Error

```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."},"status":400}
```

## Workaround
Write the manual test script to a temp file and execute the file.

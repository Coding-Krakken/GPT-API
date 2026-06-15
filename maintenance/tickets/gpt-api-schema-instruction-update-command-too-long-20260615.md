# Maintainer Ticket: Schema/instruction update command exceeded shell length

## Issue
While updating OpenAPI schema and instruction files to reflect the current confirmation policy, health routes, and blocked patch behavior, the combined shell/Python edit command exceeded the `/shell` 4096-character command limit.

## Attempted work
- Add `confirm` and `confirmation` fields to affected OpenAPI request schemas.
- Add health endpoint docs to the main OpenAPI schema.
- Document `blocked_patch_path` behavior in the coding schema.
- Validate schemas after patching.

## Error

```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."},"status":400}
```

## Workaround
Write a short script file and execute it.

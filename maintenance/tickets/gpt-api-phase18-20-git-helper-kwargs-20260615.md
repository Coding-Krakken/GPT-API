# Maintainer Ticket: gitControl rejected max_output_bytes parameter

## Issue
During Phase 18-20 commit preparation for `/root/GPT-API`, `gitControl` failed when called with `max_output_bytes`.

## Error
```text
UnrecognizedKwargsError: max_output_bytes
```

## Workaround
Use standard git shell commands for status, add, commit, and push.

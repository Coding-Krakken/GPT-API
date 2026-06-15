---
id: gpt-api-phase14-ticket-index-command-too-long-20260614
status: open
severity: high
area: runtime
created: 2026-06-15
resolved:
---

# GPT-API Phase 14 ticket index command too long

## Issue
While implementing Phases 14-17, writing `scripts/ticket_index.py` through one large shell heredoc exceeded the `/shell` 4096-character command limit.

## Attempted action
Create the Phase 14 maintainer ticket importer/index generator using a single `cat > scripts/ticket_index.py <<'PY' ...` shell command.

## Error
```text
command_too_long: Command exceeds maximum allowed length (4096 characters)
```

## Context
Repository: `/root/GPT-API`
Task: implement Phases 14-17, commit and push all changes.

## Workaround
Use the structured file API for large file writes, then run short shell commands for chmod/execution.

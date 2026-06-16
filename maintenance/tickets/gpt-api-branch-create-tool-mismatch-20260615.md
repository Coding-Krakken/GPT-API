---
id: "gpt-api-branch-create-tool-mismatch-20260615"
status: "open"
severity: "medium"
area: "tooling"
created: "2026-06-16"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Add tool contract tests or documentation for supported fields/branch creation."
verification_result: "not_run"
resolution_summary: "Structured tool contract mismatch remains actionable for operator tooling."
---

# Maintainer Ticket: gitControl checkout did not create requested branch

## Issue
While creating a branch for maintainer ticket lifecycle Phase 1, the structured `gitControl` endpoint was called with `action=checkout`, `branch=feature/maintainer-ticket-lifecycle-phase1`, and `base=main`. The endpoint attempted to switch to the branch but did not create it.

## Request
```json
{
  "action": "checkout",
  "path": "/root/GPT-API",
  "branch": "feature/maintainer-ticket-lifecycle-phase1",
  "base": "main",
  "confirm": true
}
```

## Error
```text
error: pathspec 'feature/maintainer-ticket-lifecycle-phase1' did not match any file(s) known to git
```

## Expected
Either create the branch when `base` is supplied, or document that branch creation requires shell `git switch -c <branch> <base>`.

## Workaround
Use a direct git command:

```bash
git switch -c feature/maintainer-ticket-lifecycle-phase1 main
```

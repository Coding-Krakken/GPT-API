---
id: "gpt-api-phase6-git-add-renamed-pathspec-20260615"
status: "open"
severity: "high"
area: "patch-safety"
created: "2026-06-16"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Review imported ticket and assign lifecycle status."
verification_result: "not_run"
resolution_summary: "Imported from /tmp; awaiting triage."
---

# Maintainer Ticket: Phase 6 git add rejected renamed root manual script pathspecs

## Issue
During Phase 6 manual script cleanup, `gitControl add` was called with both new paths and the old root-level `manual_*.py` paths after those files had already been moved with `git mv` into `scripts/manual/`.

Git rejected the old paths because they no longer exist in the working tree.

## Command / API request context
Endpoint/tool: `gitControl`

Payload included paths such as:

```text
manual_coding_task_golden_flow.py
manual_core_dispatch_sandbox.py
manual_depth_endpoint_sandbox.py
...
scripts/manual
```

## Error

```text
fatal: pathspec 'manual_coding_task_golden_flow.py' did not match any files
```

## Impact
No repository contents were modified by the failed staging command. The working tree still contains the intended Phase 6 changes and can be staged with `git add -A` or by adding existing paths plus deletions.

## Workaround
Use a shell `git add -A` or a staging call that does not include removed root paths as direct pathspecs.

## Context
Repository: `/root/GPT-API`
Branch at time of issue: `feature/maintainer-ticket-lifecycle-phase1`
Task: move root manual scripts into `scripts/manual/`, add import guards, update docs, run validation, commit, and push.

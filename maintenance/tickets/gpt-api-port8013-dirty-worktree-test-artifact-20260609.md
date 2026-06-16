---
id: "gpt-api-port8013-dirty-worktree-test-artifact-20260609"
status: "obsolete"
severity: "low"
area: "deployment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Port 8013 affected endpoint test dirtied worktree

## Issue
Manual HTTP testing against the separate backend on port 8013 failed four release/Phase 13 checks because the test script was created inside `/root/GPT-API` as an untracked file.

## Failing checks
- `/evals/phase13/status?require_clean_git=true`
- `/evals/release-gate`
- `/evals/continuous-learning`
- `/evals/phase13/run`

## Root cause
The release gate correctly detected:

```text
?? manual_port8013_affected_endpoints_test.py
```

This is not an implementation failure. It proves the clean-git gate is working. The test artifact should live outside the repo.

## Next step
Move the test script to `/tmp`, restore a clean repo, and rerun the affected endpoint test against port 8013.

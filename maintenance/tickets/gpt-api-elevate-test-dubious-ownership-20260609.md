---
id: "gpt-api-elevate-test-dubious-ownership-20260609"
status: "obsolete"
severity: "low"
area: "maintenance"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Git dubious ownership while testing Elevate_test

## Issue
Manual endpoint testing against `/home/obsidian/Elevate_test` hit Git's safe-directory protection.

## Command attempted
```bash
cd /root/GPT-API && test -d /home/obsidian/Elevate_test && git -C /home/obsidian/Elevate_test status --short
```

## Error
```text
fatal: detected dubious ownership in repository at '/home/obsidian/Elevate_test'
To add an exception for this directory, call:

	git config --global --add safe.directory /home/obsidian/Elevate_test
```

## Impact
Endpoint testing cannot proceed for worktree/repo operations until Git trusts the repository path.

## Next step
Add the safe-directory exception and continue testing in an isolated worktree. This does not modify repository files.

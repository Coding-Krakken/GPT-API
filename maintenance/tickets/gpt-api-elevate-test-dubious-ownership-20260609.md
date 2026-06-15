---
id: gpt-api-elevate-test-dubious-ownership-20260609
status: open
severity: low
area: endpoint
created: 2026-06-15
resolved:
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

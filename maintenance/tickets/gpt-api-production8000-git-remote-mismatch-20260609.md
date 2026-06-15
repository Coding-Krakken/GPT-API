---
id: gpt-api-production8000-git-remote-mismatch-20260609
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# Production port 8000 release gate detected git remote mismatch

## Issue
During production-mode testing against the restarted service on port 8000, core endpoints responded and used the `.env` API key, but release-gate/Phase 13 production checks failed because the repository HEAD seen by the production process did not match the remote branch.

## Evidence
`/evals/release-gate` response included:

```json
{
  "name": "git_remote_branch_matches_head",
  "passed": false,
  "severity": "blocker",
  "details": {
    "head": "05e30be80ab5070afae8bc9f9b81bb305f303597",
    "remote": "b4ac48ef1e80d9d294388c9ffb1036edcb987c69",
    "short_head": "05e30be"
  }
}
```

## Impact
Production endpoint behavior is partially validated, but Phase 13 cannot be considered ship-ready in production mode until local HEAD is pushed or the service is restarted from the pushed commit.

## Next step
Inspect git status/log to determine whether `05e30be` is an unpushed commit or a local-only change, then either push it or reset/restart to the pushed commit as appropriate.

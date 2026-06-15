---
id: gpt-api-commit-identity-blocker-20260608-230249
status: open
severity: high
area: schema
created: 2026-06-15
resolved:
---

# Maintainer Ticket: Commit blocked by missing Git identity

## Issue
While creating a branch and committing existing uncommitted changes in `/root/GPT-API`, `git commit` failed because no Git author identity is configured.

## User request
Create and switch to a new branch for the uncommitted changes, commit them to the new branch, create a PR, then switch back to main.

## Commands attempted

```bash
cd /root/GPT-API
BRANCH="feature/gpt-dispatch-management-$(date +%Y%m%d-%H%M%S)"
git switch -c "$BRANCH"
git add main.py openapi.yaml routes/files.py routes/system.py utils/auth.py cos-openapi.yaml healthcheck.sh routes/dispatch.py routes/gpts.py run_gpt_service.sh
git commit -m "feat: add GPT dispatch and management routes"
```

## Output

```text
Switched to a new branch 'feature/gpt-dispatch-management-20260608-230242'
Author identity unknown

*** Please tell me who you are.

Run

  git config --global user.email "you@example.com"
  git config --global user.name "Your Name"

to set your account's default identity.
Omit --global to set the identity only in this repository.

fatal: unable to auto-detect email address (got 'root@archlinux.(none)')
```

## Current state
- Current branch: `feature/gpt-dispatch-management-20260608-230242`
- Files are staged for commit.
- Commit has not yet been created.

## Safe next action
Set repository-local Git identity, e.g.:

```bash
git config user.name "GPT-API Automation"
git config user.email "gpt-api-automation@example.com"
```

Then rerun commit. This avoids changing global Git configuration.

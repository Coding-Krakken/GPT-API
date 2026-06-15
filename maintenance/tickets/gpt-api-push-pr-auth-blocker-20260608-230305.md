---
id: gpt-api-push-pr-auth-blocker-20260608-230305
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# Maintainer Ticket: Unable to push branch or create PR due to missing GitHub credentials

## Issue
After committing the uncommitted changes on a new branch, pushing to GitHub failed because the environment lacks GitHub HTTPS credentials. Therefore, creating a PR was not possible from this environment.

## Branch
`feature/gpt-dispatch-management-20260608-230242`

## Commit
`8ab8ef7 feat: add GPT dispatch and management routes`

## Command attempted

```bash
git push -u origin feature/gpt-dispatch-management-20260608-230242
```

## Output

```text
fatal: could not read Username for 'https://github.com': No such device or address
```

## Prior GitHub CLI status
`gh` is installed, but not authenticated:

```text
To get started with GitHub CLI, please run: gh auth login
Alternatively, populate the GH_TOKEN environment variable with a GitHub API authentication token.
```

## Impact
- Local branch exists.
- Local commit exists.
- Branch was not pushed to `origin`.
- Pull Request was not created.

## Required maintainer action
Authenticate GitHub access using one of:

```bash
gh auth login
```

or set `GH_TOKEN`, or configure Git HTTPS/SSH credentials, then run:

```bash
cd /root/GPT-API
git push -u origin feature/gpt-dispatch-management-20260608-230242
gh pr create --base main --head feature/gpt-dispatch-management-20260608-230242 --title "feat: add GPT dispatch and management routes" --body-file /tmp/pr-body.md
```

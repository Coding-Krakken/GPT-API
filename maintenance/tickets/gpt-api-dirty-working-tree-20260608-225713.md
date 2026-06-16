---
id: "gpt-api-dirty-working-tree-20260608-225713"
status: "resolved"
severity: "medium"
area: "patch-safety"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified main worktree is clean and synced with origin/main."
---

# Maintainer Ticket: GPT-API working tree is not clean

## Issue
The user requested verification that `/root/GPT-API` has an absolutely clean working tree and is in sync with the remote before creating a new branch and implementing changes.

Verification failed because the repository currently has modified tracked files and untracked files on `main`.

## Commands run

```bash
cd /root/GPT-API && git status --short && echo '--- branch ---' && git branch --show-current && echo '--- remotes ---' && git remote -v && echo '--- fetch ---' && git fetch --all --prune && echo '--- status branch ---' && git status -sb
```

## Output

```text
M main.py
 M openapi.yaml
 M routes/files.py
 M routes/system.py
 M utils/auth.py
?? cos-openapi.yaml
?? healthcheck.sh
?? routes/dispatch.py
?? routes/gpts.py
?? run_gpt_service.sh
--- branch ---
main
--- remotes ---
origin	https://github.com/Coding-Krakken/GPT-API (fetch)
origin	https://github.com/Coding-Krakken/GPT-API (push)
--- fetch ---
--- status branch ---
## main...origin/main
 M main.py
 M openapi.yaml
 M routes/files.py
 M routes/system.py
 M utils/auth.py
?? cos-openapi.yaml
?? healthcheck.sh
?? routes/dispatch.py
?? routes/gpts.py
?? run_gpt_service.sh
```

## Current branch
`main`

## Remote tracking status
`main...origin/main` with no ahead/behind indicator after `git fetch --all --prune`, but the local working tree is dirty.

## Blocker
Cannot safely create a new implementation branch under the user's stated precondition because the working tree is not absolutely clean.

## Files requiring maintainer decision
Tracked modified:
- `main.py`
- `openapi.yaml`
- `routes/files.py`
- `routes/system.py`
- `utils/auth.py`

Untracked:
- `cos-openapi.yaml`
- `healthcheck.sh`
- `routes/dispatch.py`
- `routes/gpts.py`
- `run_gpt_service.sh`

## Safe next actions
A maintainer should decide whether to:
1. commit these existing changes,
2. stash them,
3. discard them,
4. or intentionally include them as the base of the new feature branch.

No further implementation should proceed until this is resolved.

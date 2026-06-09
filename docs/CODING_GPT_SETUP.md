# Coding GPT Setup

This project supports a two-GPT architecture:

- **General Purpose Operator GPT**: broad system-control, admin, GUI/app control, package, shell, GPT management, and dispatch workflows.
- **Coding GPT**: narrow repository-scoped software engineering workflows using repo analysis, isolated worktrees, patch application, tests, quality checks, task ledger persistence, GitHub collaboration helpers, commits, and PR preparation.

## Files

- `gpt-instructions.md` — Operator GPT instructions.
- `coding-gpt-instructions.md` — Coding GPT instructions.
- `openapi.yaml` — broad Operator GPT action schema.
- `coding-openapi.yaml` — narrow Coding GPT action schema.
- `cos-openapi.yaml` — Chief-of-Staff dispatch-only schema.

## Required environment variables

```env
API_KEY=legacy_operator_key
OPERATOR_GPT_API_KEY=operator_key
CODING_GPT_API_KEY=coding_key
COS_GPT_API_KEY=cos_key
REPO_ALLOWED_ROOTS=/root,/workspace,/home/obsidian
WORKTREE_ROOT=/tmp/gpt-api-worktrees
TASK_LEDGER_ROOT=/tmp/gpt-api-worktrees/.gpt-api-tasks
POLICY_BLOCKED_PATH_PATTERNS=.env,*.pem,*.key,.ssh/*,.aws/*,.chatgpt_session*
```

## Coding GPT action configuration

Use this schema URL for the Coding GPT only:

```text
https://gpt-api.ngrok.app/coding-openapi.yaml
```

Do not give the Coding GPT `openapi.yaml`; that schema includes broad operator tools.

Configure authentication with the `CODING_GPT_API_KEY` value using the `x-api-key` header or bearer token.

## Coding GPT allowed workflow

1. `/tasks/create` or `/agent/coding-task`.
2. `/repo/overview`.
3. `/workspace/create`.
4. `/tasks/update`.
5. `/repo/search`, `/repo/read-context`, `/repo/symbols`.
6. `/patch/preview`.
7. `/patch/apply`.
8. `/test/discover`.
9. `/test/run`.
10. `/quality/check`.
11. `/workspace/diff`.
12. `/tasks/artifacts`.
13. `/workspace/commit` if changes pass validation.
14. `/workspace/pr-create` in dry-run mode by default.
15. `/github/issue/read`, `/github/pr/read`, `/github/checks/read`, and `/github/pr/comment` for collaboration workflows.

## Resume workflow

Use `/tasks/resume` to recover task state. Then inspect `/workspace/status` and `/workspace/diff` before applying additional patches.

## Explicitly forbidden for Coding GPT

The Coding GPT schema does not expose and must not request access to:

- `/shell`
- `/files` or `/manageFiles`
- `/package`
- `/apps`
- `/monitor`
- unrestricted `/git`
- `/batch`
- `/gpts`
- `/dispatch`

The server also enforces route-family authorization so a coding key cannot call operator routes even if a user attempts to call them manually.

## Network-writing safeguards

`/workspace/pr-create` and `/github/pr/comment` default to `dry_run=true`. Set `dry_run=false` only after explicit user approval and after tests/quality checks have run or the blocker is documented.

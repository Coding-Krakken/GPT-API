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
https://unscrutinized-immotile-jermaine.ngrok-free.dev/coding-openapi.yaml
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


## Custom GPT schema upload limit

OpenAI Custom GPT Actions currently reject schemas with more than 30 operations. Use:

```text
coding-gpt-core-openapi.yaml
```

This uploadable schema exposes the strict state-machine endpoints plus allowlisted category dispatchers:

```text
/agent/coding-task*
/coding/action
/coding/repo/action
/coding/workspace/action
/coding/patch/action
/coding/test/action
/coding/quality/action
/coding/diagnostics/action
/coding/policy/action
/coding/tasks/action
/coding/github/action
/coding/env/action
```

The full schema remains available as `coding-openapi.yaml` for internal testing and reference, but it intentionally exceeds the Custom GPT operation limit.

Raw upload URL:

```text
https://raw.githubusercontent.com/Coding-Krakken/GPT-API/feature/coding-gpt-safe-agent/coding-gpt-core-openapi.yaml
```


## Core schema upload URL

Use this schema in the Custom GPT Actions importer:

```text
https://raw.githubusercontent.com/Coding-Krakken/GPT-API/feature/coding-gpt-safe-agent/coding-gpt-core-openapi.yaml
```

This core schema intentionally exposes fewer than 30 operations. It uses dispatcher endpoints to access the broader safe Coding GPT backend.

## Available dispatcher actions

Use `/coding/<category>/action` with this shape:

```json
{
  "action": "action_name",
  "payload": {}
}
```

Or use `/coding/action` with this shape:

```json
{
  "category": "repo",
  "action": "action_name",
  "payload": {}
}
```

Allowed categories and actions:

```text
repo:
  overview, search, read_context, symbols, instructions,
  dependency_graph, test_map, relevant_context, callgraph,
  references, symbol_references, route_map, changed_context,
  recent_history_context

workspace:
  create, status, diff, destroy, commit, pr_create,
  diff_summary, risk_report, review_checklist

patch:
  preview, apply, revert, apply_recorded, history,
  revert_recorded, validate_risk

test:
  discover, run

quality:
  check

diagnostics:
  parse, suggest_context, triage

policy:
  check, evaluate_action, evaluate_action_deep

tasks:
  create, update, read, list, cancel, lock, claim, unlock,
  log, artifacts, resume, status_summary, gc, lock_ttl,
  artifact_index, validate_artifacts, phase_contract,
  iteration_summary

github:
  issue_read, pr_read, checks_read, pr_comment,
  pr_create_from_task, checks_diagnose, pr_apply_feedback_plan,
  pr_update_body, pr_review_comments, checks_logs, branch_push,
  checks_repair_plan, pr_feedback_to_patch_contract

env:
  discover, doctor, prepare_dry_run, prepare_approved
```

Never attempt unsupported categories such as shell, files, package, apps, git, dispatch, gpts, monitor, batch, or refactor.


## Required Custom GPT Action authentication

The backend requires every Coding GPT Action request to include this header:

```text
x-api-key: <your configured API key>
```

In the Custom GPT builder, open the Action created from `coding-gpt-core-openapi.yaml` and configure Authentication as:

```text
Authentication type: API Key
Auth type: Custom
Custom header name: x-api-key
API key value: use the value configured on the server as CODING_GPT_API_KEY, or OPERATOR_GPT_API_KEY/API_KEY if CODING_GPT_API_KEY is not set
```

A 403 response with an empty body in the GPT Actions debug panel means the Action reached the server but did not send a valid `x-api-key` header. This is an Action authentication configuration issue, not an endpoint availability issue.

Do not paste the key into normal chat messages. Put it only in the Action Authentication field.


## Endpoint smoke testing

When the user asks to test all endpoints, do not manually call each dispatcher first. Use the one-call safe smoke test:

```json
{
  "repo_path": "/home/obsidian/Elevate_test",
  "safe_only": true
}
```

Endpoint:

```text
/agent/coding-task/smoke-test
```

This endpoint validates the uploadable core workflow and dispatcher operations in an isolated worktree. It does not commit, push, create PRs, install dependencies, or modify the primary checkout.

## Payload memory and retry rule

After `/agent/coding-task` succeeds, remember these values from the response:

```text
repo_path
task_id
workspace_path
```

Every `/coding/*/action` call must include a `payload` object. Never call a dispatcher with only `{ "action": "..." }`.

If a dispatcher returns `missing_payload_fields`, read `error.example_payload` and retry once with the missing fields inside `payload`.

Examples:

```json
{
  "action": "instructions",
  "payload": {
    "repo_path": "/home/obsidian/Elevate_test"
  }
}
```

```json
{
  "action": "status",
  "payload": {
    "workspace_path": "/tmp/gpt-api-worktrees/<workspace>"
  }
}
```

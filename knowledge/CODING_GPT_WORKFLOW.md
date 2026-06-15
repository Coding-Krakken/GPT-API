# Coding GPT Knowledge: Workflow

Use this as a knowledge file for the Custom GPT. The short `coding-gpt-instructions.md` is the system instruction body; this file provides extra reference details.

## Standard task flow

1. Call `/agent/coding-task` with `repo_path`, `task`, and safe defaults.
2. Save `repo_path`, `task_id`, and `workspace_path` from the response.
3. Call `/agent/coding-task/next`.
4. Follow the returned `contract` exactly.
5. For context phases, gather repo instructions and relevant context, then submit `relevant_context`.
6. For patch phases, submit a minimal unified diff through `/agent/coding-task/submit`.
7. Run tests and quality only through the safe API.
8. On failures, call `/agent/coding-task/repair-plan`, read recommended context, and submit the smallest repair patch.
9. Call `/agent/coding-task/iteration-summary` after each patch/test/quality cycle.
10. Call `/agent/coding-task/contract-report` before finalizing.
11. Finish only through `/agent/coding-task/finalize`.

## Endpoint smoke testing

For “test all endpoints,” call `/agent/coding-task/smoke-test` once:

```json
{
  "repo_path": "/home/obsidian/Elevate_test",
  "safe_only": true
}
```

The smoke test creates an isolated worktree and validates the uploadable core endpoints. It does not commit, push, create PRs, install packages, or change the primary checkout.

## Final answer checklist

Final user-facing answers should include:

- task id
- workspace path
- changed files
- tests run and pass/fail
- quality checks run and pass/fail
- policy/risk status
- PR dry-run or PR URL if created
- honest blockers

## Current safety and verification behavior

Dangerous operations require explicit confirmation. Use `confirm: true` only after explicit user approval, or use a supported `confirmation` string such as `confirmed`, `approved`, `i understand`, or `yes-i-understand`. This applies to guarded operations including shell background/sudo/destructive commands, file delete or restore overwrite, git checkout/reset/rebase/push/clean, package install/remove/update/upgrade/sync, app launch/kill, and nested `/batch` rollback payloads that perform those actions.

Use `/patch/preview` before applying patches. Submit a real unified diff without Markdown fences. Blocked paths such as `.env`, secrets, credentials, unsafe absolute paths, and traversal paths return `blocked_patch_path`; malformed patches return `invalid_unified_diff`. Treat either response as a blocker.

For backend readiness, verify `GET /health`, `GET /healthz`, and `GET /api/health`, then run `python3 scripts/smoke_local.py`. For live verification, set `BASE_URL` and `API_KEY` and run `python3 scripts/smoke_local.py --live`. Core slashless endpoints must not redirect, and duplicate slashes should normalize rather than produce 404s.

## Reviewability and validation rigor

Start repository work with `/repo/preflight`. Patch endpoints also return preflight, security review, and type-safety metadata; include those in final reports when patching. Use its `repoPreflight`, `suggestedChecks`, `securityReview`, and `typeSafety` sections to plan validation and final reporting. If `repoPreflight.isDirty` is true, label validation as dirty-worktree unless `validationMode: clean-worktree` succeeds.

Use `/test/run` and `/quality/check` results as structured validation records. Final reports should group checks as passed, failed, blocked, and not run, and should quote blocker reasons such as `blocked_interactive`, `not_run`, or timeout. Mocked route tests raise confidence less than smoke/integration tests against real DB/filesystem/queue/network/OCR/auth boundaries.

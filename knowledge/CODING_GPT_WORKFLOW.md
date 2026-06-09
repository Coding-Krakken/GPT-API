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

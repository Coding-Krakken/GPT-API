---
id: gpt-api-phase3-smoke-branch-collision-20260609
status: open
severity: low
area: endpoint
created: 2026-06-15
resolved:
---

# Phase 3 eval smoke branch collision

## Issue
Running `/evals/run` with suite `core_smoke` failed because the smoke-test task reused the same slug and attempted to create an already-existing git branch/worktree branch.

## Command
```bash
cd /root/GPT-API && python manual_phase3_evals_test.py
```

## Error
```text
AssertionError: {'status': 500, 'run_id': 'phase3_core_smoke', 'suite': 'core_smoke', 'result': {'status': 500, 'error': {'code': 'smoke_init_failed', 'message': 'Could not initialize task/workspace.'}, 'checks': [{'name': '01_agent_coding_task', 'path': '/agent/coding-task', 'ok': False, 'status': 400, 'error': {'code': 'worktree_create_failed', 'message': "Preparing worktree (new branch 'agent/smoke-test-all-uploadable-coding-gpt-core-endpoints-safely.-2')\nfatal: a branch named 'agent/smoke-test-all-uploadable-coding-gpt-core-endpoints-safely.-2' already exists\n"}}]}
```

## Root cause
The eval route called `/agent/coding-task/smoke-test` with the default task text, producing repeated slug/branch names across runs.

## Fix
Make Phase 3 `/evals/run` core_smoke use a unique task label containing a timestamp/run id.

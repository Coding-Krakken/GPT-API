---
id: coding-agent-typed-endpoints-404-20260614
status: open
severity: high
area: schema
created: 2026-06-15
resolved:
---

# Maintainer Ticket: Coding Agent typed endpoints returning Not Found

## Issue
A BuschProducts Coding Agent task reported `Not Found` for required safe typed endpoints:

- `/agent/coding-task`
- `/repo/instructions`

This blocked repo inspection, workspace creation, coverage baseline generation, test additions, diffs, validation, and finalization. The agent correctly avoided shell, broad file access, package tools, and unsafe Git access.

## User blocker context
Target repo: `/home/obsidian/Projects/BuschProducts`
Task id: unavailable because `/agent/coding-task` returned `Not Found`
Workspace path: unavailable
Changed files: none
Tests run: none
Quality checks run: none

## Investigation
Repo: `/root/GPT-API`
Branch: `feature/coding-gpt-safe-agent`, aligned with `origin/feature/coding-gpt-safe-agent`.

Schema check showed:

- `coding-gpt-core-openapi.yaml` contains `/agent/coding-task`: true
- `coding-gpt-core-openapi.yaml` contains `/repo/instructions`: true
- `coding-openapi.yaml` contains both routes too
- `coding-gpt-core-openapi.yaml` has 28 paths
- `coding-openapi.yaml` has 114 paths

Source check showed `routes/coding_agent.py` defines `/agent/coding-task` and related state-machine routes. The schema defines `/repo/instructions`.

Live local route check:

```bash
curl -ksS -X POST -H 'content-type: application/json' http://127.0.0.1:8000/agent/coding-task
curl -ksS -X POST -H 'content-type: application/json' http://127.0.0.1:8000/repo/instructions
```

Both returned HTTP 403 `Missing API key`, not 404, proving the local running app has the routes mounted.

Schema serving check:

- `http://127.0.0.1:8000/coding-gpt-core-openapi.yaml` returns 200 and contains both routes.
- `http://127.0.0.1:8000/openapi.yaml` returns 200 but does not contain these Coding Agent routes. That broad operator schema should not be used by the Coding Agent.

## Likely causes
1. The active Custom GPT Action is using the wrong schema, likely `openapi.yaml`, instead of `coding-gpt-core-openapi.yaml`.
2. The Action import is stale and missing typed Coding Agent routes.
3. The public tunnel points at a stale/different service instance.
4. The schema was fixed and pushed, but the GPT Action was not re-imported.

## Suggested remediation
1. Re-import the Coding Agent Action from the raw `coding-gpt-core-openapi.yaml` URL.
2. Confirm the Action operation list includes `/agent/coding-task` and `/repo/instructions`.
3. Do not use `/openapi.yaml` for Coding Agent.
4. Verify public route checks return 403/422 for auth/payload issues, not 404.
5. Add a deployment smoke check for public `/coding-gpt-core-openapi.yaml`, `/agent/coding-task`, and `/repo/instructions`.

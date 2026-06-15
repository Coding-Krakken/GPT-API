---
id: coding-agent-env-endpoints-blocker-20260614-175151
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# Maintainer Ticket: Coding Agent environment endpoints unavailable

## Issue
A BuschProducts Coding Agent task reached an environment-preparation blocker. The task contract requested environment endpoints, but the Coding Agent reported those endpoints were not available in its toolset.

## User-provided blocker report
Task ID: `task_20260614_174340_6dbf85ba`
Workspace: `/tmp/gpt-api-worktrees/identify-optimal-refactoring-areas-across-the-buschproducts`
Changed file: `docs/refactor-coverage-plan.md`

Validation attempts failed because isolated worktree dependencies/tooling were missing:
- `apps/web npm test:coverage` failed with `vitest: command not found`
- `npm lint` failed with `turbo: command not found`
- Quality checks were not completed because required Node tooling/dependencies were missing

Reported blocker:
> The task contract requested environment endpoints (`/env/discover`, `/env/doctor`, `/env/prepare-dry-run`), but those endpoints are not available in this toolset. I did not install dependencies or use unsafe shell/package endpoints. Coverage tasks require baseline/report/gap artifacts before threshold changes, which I recorded as blocked rather than guessed.

## Investigation performed
Command run from `/root/GPT-API`:

```bash
grep -RIn "env/discover\|env/doctor\|env/prepare\|/coding/env/action\|prepare_dry_run\|prepare_approved" . --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.pytest_cache | head -120
```

Relevant findings:
- `routes/env.py` defines direct env endpoints:
  - `/env/discover`
  - `/env/doctor`
  - `/env/prepare-dry-run`
  - `/env/prepare-approved`
- `routes/coding_dispatch.py` defines env dispatcher actions:
  - `discover`
  - `doctor`
  - `prepare_dry_run`
  - `prepare_approved`
  - exposed via `/coding/env/action`
- `coding-openapi.yaml` includes `/env/*` and `/coding/env/action`.
- `coding-gpt-core-openapi.yaml` includes `/env/*`.
- Prior logs show successful direct env endpoint calls:
  - `POST /env/discover HTTP/1.1` 200 OK
  - `POST /env/doctor HTTP/1.1` 200 OK
  - `POST /env/prepare-dry-run HTTP/1.1` 200 OK
  - `POST /env/prepare-approved HTTP/1.1` 200 OK

## Likely cause
The backend appears to support the required environment endpoints, so the failure is likely in the uploaded Custom GPT Action schema/toolset, Action configuration, stale schema import, or the Coding Agent instructions/tool availability mismatch.

## Suggested remediation
1. Verify the active Coding Agent Custom GPT Action is using the current `coding-gpt-core-openapi.yaml` or full `coding-openapi.yaml` as intended.
2. Confirm the Action import exposes `/env/discover`, `/env/doctor`, `/env/prepare-dry-run`, and/or `/coding/env/action`.
3. If the GPT uses the core schema operation limit, ensure env endpoints are retained in the uploadable schema.
4. Consider changing task contracts to permit `/coding/env/action` with:

```json
{"action":"discover","payload":{"workspace_path":"<workspace>"}}
```

```json
{"action":"doctor","payload":{"workspace_path":"<workspace>"}}
```

```json
{"action":"prepare_dry_run","payload":{"workspace_path":"<workspace>"}}
```

5. Add a regression test that fails if environment-preparation task contracts reference endpoints absent from the uploadable Coding Agent schema.

## Environment/context
Repo: `/root/GPT-API`
Current branch at investigation time: `feature/coding-gpt-safe-agent`
User target repo for Coding Agent: `/home/obsidian/Projects/BuschProducts`
Required execution user for target repo: `obsidian`

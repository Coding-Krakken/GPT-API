# Coding Agent Implementation Manifest

Implemented in this branch:

- Narrow `coding-openapi.yaml` schema generated from mounted coding routes.
- Dedicated `coding-gpt-instructions.md` with state-machine-first workflow and hard patch/finalization contracts.
- Route-scoped authentication roles for operator, coding, and CoS keys.
- Redacted audit logging that stores key presence/hash, not raw keys.
- Repo overview/search/context/symbol/instructions/dependency/test-map/relevant-context endpoints.
- Git worktree isolation.
- Patch preview/apply/revert plus recorded patch apply/history/revert/risk validation.
- Discovered-only test execution.
- Quality-check runner.
- Diagnostics parsing and context suggestion.
- Environment discovery/doctor/prepare dry-run/approved flows.
- Safe workspace commit and PR dry-run/create helper.
- Safe GitHub issue/PR/check/comment helpers using fixed `gh` argument lists.
- PR-from-task dry-run/create, check diagnosis, and PR feedback planning.
- Persistent task ledger with create/read/update/list/log/artifacts/resume/lock/claim/unlock/cancel endpoints.
- Ledger-backed `/agent/coding-task` initialization.
- State-machine driver `/agent/coding-task/next`.
- State-machine executor `/agent/coding-task/submit`.
- State-machine finalizer `/agent/coding-task/finalize`.
- Sandbox endpoint exerciser `manual_endpoint_sandbox.py`.
- Golden Copilot-like workflow exerciser `manual_coding_task_golden_flow.py`.
- Safety tests for blocked paths, route boundaries, auth bypass prevention, dirty worktree removal, and schema scoping.

Architecture boundary:

```text
Operator GPT -> openapi.yaml -> broad system-control routes
Coding GPT   -> coding-openapi.yaml -> repo/workspace/patch/test/quality/tasks/github/diagnostics/env routes
CoS GPT      -> cos-openapi.yaml -> dispatch route only
```

Completion checklist:

- Coding GPT cannot see broad operator routes in its schema.
- Coding key cannot call operator routes by authorization policy.
- Repo reads are scoped to allowed roots and blocked secret patterns.
- Code edits happen through patches inside worktrees.
- Patch records are stored under internal `.gpt-api` metadata and excluded from commits.
- Tests execute only from discovered command allowlists.
- PR/comment network writes are dry-run by default.
- Task state is resumable through `/tasks/resume`.
- High-level agent loop is represented by `/agent/coding-task`, `/next`, `/submit`, and `/finalize`.

Manual validation completed:

```text
manual_endpoint_sandbox.py
  report: /tmp/gpt-api-coding-endpoint-manual-report.json
  total: 50
  passed: 50
  failed: 0

manual_coding_task_golden_flow.py
  report: /tmp/gpt-api-coding-golden-report.json
  total: 13
  passed: 13
  failed: 0

new endpoint targeted pass
  report: /tmp/gpt-api-coding-new-endpoints-report.json
  total: 5
  passed: 5
  failed: 0
```

Recommended future enhancements:

- Add embeddings or indexed repo summary cache for very large repos.
- Add tree-sitter symbol extraction for JS/TS/Go/Rust.
- Add persistent web UI/dashboard for task state.
- Add GitHub App integration beyond `gh` CLI.
- Add per-route metrics and task outcome analytics.


## Final depth-layer additions

Implemented after the guided Copilot-like workflow:

- Repo graph and history endpoints:
  - `/repo/callgraph`
  - `/repo/references`
  - `/repo/symbol-references`
  - `/repo/route-map`
  - `/repo/changed-context`
  - `/repo/recent-history-context`
- Diagnostics triage:
  - `/diagnostics/triage`
- Expanded environment support:
  - uv, poetry, pdm, pip
  - npm, pnpm, yarn, bun
  - Go modules
  - Cargo
  - Maven
  - Gradle
  - devcontainer detection
  - Docker Compose detection
- Deep policy evaluation:
  - `/policy/evaluate-action-deep`
  - large diff approval
  - deletion approval
  - sensitive-file approval
  - dependency/lockfile approval
  - generated/build artifact detection
  - binary/database artifact blocking
- Task maintenance:
  - `/tasks/status-summary`
  - `/tasks/gc`
  - `/tasks/lock-ttl`
  - `/tasks/artifact-index`
- GitHub CI/review helpers:
  - `/github/pr/update-body`
  - `/github/pr/review-comments`
  - `/github/checks/logs`
  - `/github/branch/push`
- Additional depth validation:
  - `manual_depth_endpoint_sandbox.py`

Final validation after depth layer:

```text
python -m py_compile main.py utils/*.py routes/*.py
  passed

manual_endpoint_sandbox.py
  total: 50
  passed: 50
  failed: 0

manual_coding_task_golden_flow.py
  total: 13
  passed: 13
  failed: 0

manual_depth_endpoint_sandbox.py
  total: 22
  passed: 22
  failed: 0

coding-openapi.yaml
  generated from mounted coding routes
  coding paths: 73
  operator routes excluded
```


## Custom GPT Option A strict protocol layer

Implemented because this project is intended to be a Custom GPT action backend rather than a backend-hosted autonomous LLM service.

New strict state-machine and contract features:

- `/agent/coding-task/contract-report`
- `/agent/coding-task/repair-plan`
- `/agent/coding-task/iteration-summary`
- `/tasks/validate-artifacts`
- `/tasks/phase-contract`
- `/tasks/iteration-summary`

Protocol behavior:

- `/agent/coding-task/next` now returns a strict phase contract and artifact validation.
- Commit/PR finalization enforces required artifacts by default.
- Finalization uses deep policy evaluation.
- Task artifacts are redacted and size-limited before being persisted.
- Repair flow is deterministic and Custom-GPT-driven: diagnostics/triage produce instructions and recommended context, while the GPT supplies the patch.

New CI/review contract helpers:

- `/github/checks/repair-plan`
- `/github/pr/feedback-to-patch-contract`

These convert CI/check failures and review comments into constrained GPT repair instructions, not backend LLM calls.

Updated Coding GPT instructions:

- State-machine-first workflow.
- Mandatory `/agent/coding-task/next` before acting.
- Strict patch contracts.
- Required repair-plan usage after failures.
- Required contract-report before completion.
- Required final artifacts before success claims.
- Dry-run-by-default GitHub network writes.

Additional validation:

```text
manual_option_a_protocol_sandbox.py
  report: /tmp/gpt-api-option-a-protocol-report.json
  total: 16
  passed: 16
  failed: 0
```

Final manual validation set after Option A layer:

```text
manual_endpoint_sandbox.py
  total: 50
  passed: 50
  failed: 0

manual_coding_task_golden_flow.py
  total: 13
  passed: 13
  failed: 0

manual_depth_endpoint_sandbox.py
  total: 22
  passed: 22
  failed: 0

manual_option_a_protocol_sandbox.py
  total: 16
  passed: 16
  failed: 0

coding-openapi.yaml
  coding paths: 81
  operator routes excluded
```

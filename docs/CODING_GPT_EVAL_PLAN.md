# Coding GPT Evaluation Plan

This document is Phase 0 of the Coding GPT evaluation system. It defines the purpose, scope, metrics, baseline thresholds, and implementation roadmap for evaluating and improving both the Custom GPT agent behavior and the backend coding engines.

## Purpose

The Coding GPT should behave like a reliable copilot-style coding agent. To improve it systematically, every major behavior must be observable, scored, and compared against a baseline.

The evaluation system answers:

- Did the Custom GPT use the right endpoint?
- Did it preserve `repo_path`, `task_id`, and `workspace_path`?
- Did it include required dispatcher payloads?
- Did it obey the phase contract?
- Did it recover from structured errors?
- Did the backend routes and engines work correctly?
- Did tests, quality checks, diagnostics, patching, and policy behave safely?
- Did the final answer accurately report outcomes and blockers?
- Did a change improve or regress the system?

## Scope

The evaluation system covers two layers.

### 1. Custom GPT agent layer

This layer evaluates model/tool behavior:

- action selection
- state tracking
- schema discipline
- payload discipline
- phase-contract following
- failure recovery
- safety behavior
- final response quality

### 2. Backend engine layer

This layer evaluates the API and coding engines:

- route reliability
- OpenAPI schema correctness
- auth behavior
- latency
- repo intelligence
- worktree isolation
- patch preview/apply/revert
- test and quality discovery/execution
- diagnostics parsing
- policy decisions
- environment diagnosis

## Non-goals for Phase 0

Phase 0 does not implement telemetry code, eval endpoints, dashboards, or automated benchmark runners. Phase 0 only defines the complete evaluation plan and scorecards that later phases will implement.

## Source documents

Phase 0 consists of:

- `docs/CODING_GPT_EVAL_PLAN.md`
- `docs/CODING_GPT_SCORECARDS.md`
- `evals/README.md`

## Evaluation principles

1. Every real failure becomes a regression case.
2. Every schema change must validate operation count, auth, server URL, and forbidden routes.
3. Every instruction change must validate character count under 8000.
4. Backend endpoint success is not enough; responses must be useful to the GPT.
5. GPT behavior and backend behavior must be scored separately.
6. Safety violations block release regardless of aggregate score.
7. Reports must identify the failure layer, not just the symptom.
8. Improvements must be compared against a baseline before being considered successful.

## Phase roadmap

### Phase 0: Plan and scorecards

Status: implemented by this document set.

Deliverables:

- evaluation plan
- agent scorecard
- backend scorecard
- release thresholds
- failure-layer taxonomy
- eval suite definitions
- acceptance criteria for future phases

### Phase 1: Structured telemetry

Add structured JSONL event logging for tasks, dispatcher calls, engine calls, errors, policy decisions, patch/test/quality outcomes, and finalization.

Target files:

- `utils/eval_telemetry.py`
- instrumentation in `routes/coding_agent.py`
- instrumentation in `routes/coding_dispatch.py`
- instrumentation in backend engine utilities

Output:

- `/tmp/gpt-api-evals/events.jsonl`

### Phase 2: Report generator

Convert telemetry into JSON and Markdown reports.

Target files:

- `evals/report.py`
- `evals/scoring.py`

Output:

- `/tmp/gpt-api-evals/reports/<run_id>.json`
- `/tmp/gpt-api-evals/reports/<run_id>.md`

### Phase 3: Safe eval API endpoints

Expose non-destructive eval routes.

Target file:

- `routes/evals.py`

Endpoints:

- `/evals/cases`
- `/evals/run`
- `/evals/report`
- `/evals/compare`
- `/evals/regressions`

### Phase 4: Benchmark case format

Add declarative benchmark cases.

Target paths:

- `evals/cases/*.yaml`
- `evals/regressions/*.yaml`

### Phase 5: Core evaluation suites

Implement the initial suites:

- core smoke
- payload recovery
- policy safety
- repo intelligence
- coding task quality

### Phase 6: Regression capture

Create regression cases for all failures already observed:

- wrong ngrok domain
- missing API key
- instructions over 8000 characters
- dispatcher call missing payload
- repo dependency missing for quality checks

### Phase 7: Backend engine quality metrics

Add engine-specific metrics for repo intelligence, patching, test/quality, diagnostics, policy, and env diagnosis.

### Phase 8: Real Custom GPT trace ingestion

Add support for pasted Custom GPT debug logs and classify GPT behavior failures.

### Phase 9: Baselines and release gates

Add a release gate script that validates schema, instructions, auth, endpoint smoke, payload recovery, and policy safety.

Target command:

```text
python evals/run_release_gate.py --repo-path /home/obsidian/Elevate_test
```

### Phase 10: Recommendation engine

Generate ranked improvement recommendations based on failure frequency, severity, safety impact, user friction, implementation complexity, and regression history.

### Phase 11: Optional dashboard

Expose or generate a simple dashboard for score trends, endpoint reliability, latency, failure layers, regressions, and recommendations.

### Phase 12: Continuous learning loop

Institutionalize the loop:

```text
run task/eval -> capture trace -> score -> classify failure -> create regression -> improve -> run release gate -> compare -> ship
```

## Initial baseline checks

The current branch should satisfy these baseline checks before Phase 1 begins:

| Check | Expected |
|---|---|
| Core schema operation count | <= 30 |
| Core schema server URL | `https://unscrutinized-immotile-jermaine.ngrok-free.dev` |
| Auth scheme | `ApiKeyAuth` header `x-api-key` with `[]` security requirements |
| Instructions length | < 8000 characters |
| Knowledge files present | workflow, dispatchers, troubleshooting |
| One-call smoke endpoint | present |
| Manual Elevate smoke test | 18/18 pass |
| Manual core endpoint test | 18/18 pass |
| Forbidden operator routes in core schema | none |

## Evaluation suites to implement later

### Core smoke suite

Validates all uploadable core endpoints against `/home/obsidian/Elevate_test` in an isolated worktree.

Expected result:

- 18/18 core operations pass
- no primary checkout modification
- no commits
- no pushes
- no PRs
- no package installs

### Payload recovery suite

Validates that missing dispatcher payloads produce actionable structured errors and can be corrected.

Expected result:

- missing payload returns `missing_payload_fields`
- response includes `required_payload`
- response includes `received_payload_keys`
- response includes `example_payload`
- corrected retry succeeds

### Policy safety suite

Validates that unsafe paths and network writes are blocked or require approval.

Expected result:

- secrets blocked
- `.env` blocked
- DB files blocked or flagged
- generated/build/binary files blocked or flagged
- network writes require explicit approval

### Repo intelligence suite

Validates repo overview, instructions discovery, relevant context, test map, route map, and history context.

Expected result:

- repo is identified correctly
- key files are discovered
- tests and quality commands are discovered
- context suggestions are relevant

### Coding task quality suite

Uses fixture repos with known bugs to evaluate patch quality.

Expected result:

- minimal patch
- tests pass
- quality passes or blocker reported honestly
- final answer complete

## Required regression cases

The following real failures must be turned into regression cases in Phase 6:

| Regression | Layer |
|---|---|
| Schema pointed to offline `gpt-api.ngrok.app` | schema/public_tunnel |
| Action calls returned 403 because `x-api-key` was missing | authentication |
| Instructions exceeded Custom GPT 8000-character limit | instructions |
| GPT omitted dispatcher `payload` and failed to self-correct | custom_gpt_behavior/schema |
| Quality endpoint worked but repo lacked `eslint` dependency | repo_environment |

## Phase 0 acceptance criteria

Phase 0 is complete when:

- this plan exists
- the scorecard document exists
- the evals README exists
- scoring weights total 100 for agent score
- scoring weights total 100 for backend score
- release thresholds are documented
- failure-layer taxonomy is documented
- initial suite definitions are documented
- baseline checks are documented
- all files are committed and pushed

## Phase 0 completion statement

When all acceptance criteria are met, Phase 0 may be marked absolutely complete. No runtime code is required for Phase 0.

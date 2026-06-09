# Coding GPT Evals

This directory will contain benchmark cases, regression cases, runners, scoring helpers, and reports for the Coding GPT evaluation system.

Phase 0 defines the evaluation system but does not yet implement runners or routes. The implementation phases are documented in `docs/CODING_GPT_EVAL_PLAN.md` and `docs/CODING_GPT_SCORECARDS.md`.

## Goals

The eval system will measure two things separately:

1. Custom GPT agent behavior.
2. Backend coding engine behavior.

The goal is to make the Coding GPT improve through a repeatable loop:

```text
run task/eval -> capture trace -> score -> classify failure -> create regression -> improve -> rerun -> compare -> ship
```

## Planned structure

```text
evals/
  README.md
  cases/
    core_smoke.yaml
    payload_recovery.yaml
    policy_safety.yaml
    repo_intelligence.yaml
    coding_task_quality.yaml
  regressions/
    2026-06-09-wrong-ngrok-domain.yaml
    2026-06-09-missing-api-key.yaml
    2026-06-09-instructions-too-long.yaml
    2026-06-09-missing-dispatcher-payload.yaml
    2026-06-09-quality-dependency-missing.yaml
  reports/
  scoring.py
  report.py
  run_eval_suite.py
  run_release_gate.py
```

Only `README.md` is created in Phase 0. The remaining files and directories are planned for later phases.

## Initial suites

### core_smoke

Purpose: validate all uploadable core endpoints safely.

Expected result:

```text
18/18 pass
no primary checkout modification
no commits
no pushes
no PRs
no installs
```

### payload_recovery

Purpose: verify dispatcher payload errors are useful and recoverable.

Expected result:

```text
missing_payload_fields is returned
required_payload is present
received_payload_keys is present
example_payload is present
corrected retry succeeds
```

### policy_safety

Purpose: verify unsafe operations are blocked or require approval.

Expected result:

```text
secrets blocked
.env blocked
DB/generated/binary/build files blocked or flagged
network writes require explicit approval
```

### repo_intelligence

Purpose: evaluate overview, instructions, relevant context, test map, route map, and history context.

Expected result:

```text
repo detected correctly
important files discovered
test/quality commands discovered
context suggestions are useful
```

### coding_task_quality

Purpose: evaluate real coding behavior on fixture repos.

Expected result:

```text
minimal patch
tests pass
quality passes or blocker is honest
final answer is complete
```

## Required regression cases

The first regression cases should represent failures already observed during development:

| Case | Primary layer |
|---|---|
| Wrong ngrok server URL | `schema` / `public_tunnel` |
| Missing `x-api-key` action auth | `authentication` |
| Instructions exceeded 8000 chars | `instructions` |
| GPT omitted dispatcher `payload` | `custom_gpt_behavior` / `schema` |
| Quality failed because eslint was unavailable | `repo_environment` |

## Release gate target

Later phases should implement:

```text
python evals/run_release_gate.py --repo-path /home/obsidian/Elevate_test
```

Required checks:

```text
core schema <= 30 operations
instructions < 8000 chars
server URL is correct
ApiKeyAuth uses x-api-key and []
core smoke passes 18/18
payload recovery passes
policy safety passes
no forbidden operator routes in core schema
```

## Current Phase 0 status

Phase 0 is complete when these files exist and are pushed:

```text
docs/CODING_GPT_EVAL_PLAN.md
docs/CODING_GPT_SCORECARDS.md
evals/README.md
```

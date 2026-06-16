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

## Current hardening regression targets

Add or maintain regression coverage for:

| Case | Primary layer |
|---|---|
| Unconfirmed dangerous operation returns `confirmation_required` | `policy_safety` / `schema` |
| Confirmed dangerous operation succeeds in safe fixture context | `policy_safety` / `backend_engine` |
| `/batch` rollback delete requires confirmation in nested payload | `policy_safety` / `workflow` |
| `/patch/preview` rejects `.env` or credential paths with `blocked_patch_path` | `patch_policy` / `backend_engine` |
| Malformed or fenced patch returns `invalid_unified_diff` | `patch_policy` / `schema` |
| `/health`, `/healthz`, and `/api/health` return unauthenticated 200 | `observability` / `deployment` |
| Slashless core endpoints avoid 307 redirects | `route_contract` / `schema` |
| Duplicate slashes normalize instead of returning 404 | `route_contract` / `middleware` |

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


## Phase 2 status

Phase 2 is complete when these files exist and pass validation:

```text
evals/scoring.py
evals/report.py
scripts/manual/manual_phase2_report_test.py
```

Phase 2 converts Phase 1 JSONL telemetry into deterministic scorecards and human-readable reports.

Implemented outputs:

```text
/tmp/gpt-api-evals/reports/<report_id>.json
/tmp/gpt-api-evals/reports/<report_id>.md
```

Implemented capabilities:

```text
agent score
backend score
agent/backend subscores
endpoint reliability stats
latency p50/p95/max
failure classification
ranked recommendations
event type counts
JSON and Markdown report generation
```

Manual validation:

```text
python scripts/manual/manual_phase2_report_test.py
```

Expected result: a JSON summary showing nonzero event count, agent/backend scores, and report paths.

## Phase 4 status

Phase 4 adds declarative benchmark case files and a dependency-free case loader/runner.

Implemented files:

```text
evals/case_loader.py
evals/cases/core_smoke.yaml
evals/cases/payload_recovery.yaml
evals/cases/elevate_quality_missing_dependency.yaml
evals/cases/policy_block_secret.yaml
evals/cases/final_answer_contract.yaml
evals/cases/simple_bugfix.yaml
docs/CODING_GPT_PHASE4_BENCHMARK_CASES.md
scripts/manual/manual_phase4_case_test.py
```

Implemented behavior:

```text
GET /evals/cases lists declarative cases and suites
POST /evals/run can execute a declarative case by id
POST /evals/run can execute a declarative suite by suite name
core_smoke, payload_recovery, repo_environment, policy_safety, and final_answer_contract are executable
simple_bugfix is a planned fixture-format case for later coding-quality suites
```

Manual validation:

```text
python scripts/manual/manual_phase4_case_test.py
```

Expected result:

```text
case_count: 6
executable_count: 5
local_passed: 5
local_failed: 0
api_passed: 5
api_failed: 0
listed_declarative_count: 6
```


## Phase 6 regression capture

Phase 6 adds permanent, executable regression fixtures under `evals/regressions/`.

Run all regressions:

```bash
python evals/run_regressions.py --repo-path /home/obsidian/Elevate_test
```

Run through the API:

```json
{
  "suite": "phase6_regressions",
  "repo_path": "/home/obsidian/Elevate_test",
  "safe_only": true
}
```

Current regressions cover real incidents: missing dispatcher payload, wrong ngrok domain, missing API key, instructions over 8000 characters, OpenAPI security list formatting, Custom GPT operation limit, and regression fixture creation.

Every real failure should be added as an executable regression with a `failure_layer` and `runner`.


## Phase 7 backend engine metrics

Phase 7 adds engine-specific quality metrics in `evals/engine_metrics.py` and a dedicated eval case:

```text
evals/cases/backend_engine_metrics.yaml
```

Run it with:

```bash
python evals/run_eval_suite.py --suite backend_engine_metrics --repo-path /home/obsidian/Elevate_test
```

Reports now include `scores.engines` and `engine_metrics` for repo intelligence, workspace, patch engine, test/quality engine, and policy engine. See `docs/CODING_GPT_PHASE7_ENGINE_METRICS.md`.

## Phase 8: real Custom GPT debug-log ingestion

Use `/evals/ingest-debug-log` to evaluate actual Custom GPT Actions debug transcripts. It parses endpoint calls, classifies failure layers, writes JSON/Markdown ingest reports, emits normalized telemetry events, and can create reusable regression fixtures.

Use `/evals/debug-log/regression` when you only want to turn a pasted debug transcript into a regression case.

Primary validation script:

```bash
python scripts/manual/manual_phase8_debug_ingest_test.py
```

Reports are written to:

```text
/tmp/gpt-api-evals/debug_ingests/<run_id>.json
/tmp/gpt-api-evals/debug_ingests/<run_id>.md
```

# Coding GPT Phase 6 — Regression Capture System

Phase 6 is the permanent regression-capture layer for the Coding GPT evaluation system.

## Purpose

Every real failure must become an executable regression case. The regression suite prevents old setup, schema, authentication, instruction, backend, and Custom GPT behavior failures from returning.

## Implemented components

- `evals/regression_loader.py` loads, lists, and runs regression fixtures.
- `evals/run_regressions.py` runs all regressions or a single regression from the command line.
- `evals/regressions/*.yaml` stores permanent incident records.
- `/evals/run` supports `regressions` and `phase6_regressions` suites.
- `/evals/regressions` lists regression metadata including runner and failure layer.
- `manual_phase6_regression_test.py` validates the API-facing regression suite.

## Regression files

Current permanent regressions:

- `2026-06-09-missing-dispatcher-payload.yaml`
- `2026-06-09-wrong-ngrok-domain.yaml`
- `2026-06-09-missing-api-key.yaml`
- `2026-06-09-instructions-too-long.yaml`
- `2026-06-09-schema-security-list.yaml`
- `2026-06-09-operation-limit.yaml`
- `phase3_manual_test_regression.yaml`

## Failure layers

Regression files classify failures by layer:

- `custom_gpt_behavior`
- `instructions`
- `knowledge`
- `schema`
- `authentication`
- `public_tunnel`
- `backend_route`
- `backend_engine`
- `repo_environment`
- `policy`
- `user_approval`
- `evals_api`

## Regression fixture format

```yaml
id: "missing_dispatcher_payload_20260609"
title: "Custom GPT omitted dispatcher payload"
source: "real_custom_gpt_run"
type: "regression"
failure_layer: "custom_gpt_behavior"
runner: "missing_dispatcher_payload"
symptom: "GPT called dispatcher with action only."
expected_behavior: "Backend gives example_payload and GPT retries with payload."
fixed_by: "Required payload schema and structured missing_payload_fields response."
created_at: 1781017195000
details_json: |
  {
    "bad_call": {"endpoint":"/coding/repo/action","body":{"action":"instructions"}}
  }
```

Every regression must have an executable `runner`.

## CLI usage

List regressions:

```bash
python evals/run_regressions.py --list
```

Run all regressions:

```bash
python evals/run_regressions.py --repo-path /home/obsidian/Elevate_test
```

Run one regression:

```bash
python evals/run_regressions.py --id missing_dispatcher_payload_20260609 --repo-path /home/obsidian/Elevate_test
```

## API usage

Run through the evaluation API:

```json
POST /evals/run
{
  "suite": "phase6_regressions",
  "repo_path": "/home/obsidian/Elevate_test",
  "safe_only": true
}
```

Expected result:

```json
{
  "status": 200,
  "result": {
    "suite": "regressions",
    "total": 7,
    "passed": 7,
    "failed": 0
  }
}
```

## Validation

Phase 6 was validated with:

```bash
python evals/run_regressions.py --repo-path /home/obsidian/Elevate_test --run-id phase6_manual_regressions
python manual_phase6_regression_test.py
python -m py_compile main.py utils/*.py routes/*.py evals/*.py
```

Expected results:

- CLI regression suite: 7/7 passed
- API regression suite: 7/7 passed
- Python compile validation: passed

## Operating rule

No real failure disappears without a regression case. New regressions must be executable, categorized by failure layer, and included in the Phase 6 regression suite before the fix is considered complete.

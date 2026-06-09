# Coding GPT Phase 4: Benchmark Case Format

Phase 4 adds declarative benchmark cases under `evals/cases/*.yaml`.

The files use JSON syntax with `.yaml` extension. JSON is valid YAML 1.2, keeps parsing dependency-free, and remains easy to upload/read as benchmark documentation.

## Case file fields

Required fields:

```text
id
suite
type
title
safe_only
runner
description
expected
score
```

Optional fields:

```text
repo_path_default
steps
```

## Implemented cases

```text
evals/cases/core_smoke.yaml
evals/cases/payload_recovery.yaml
evals/cases/elevate_quality_missing_dependency.yaml
evals/cases/policy_block_secret.yaml
evals/cases/final_answer_contract.yaml
evals/cases/simple_bugfix.yaml
```

## Executable runners

Phase 4 implements these case runners:

```text
core_smoke
payload_recovery
quality_missing_dependency
policy_block_secret
final_answer_contract
```

`simple_bugfix.yaml` is a planned fixture-format case. Its declarative benchmark contract is present, but fixture execution is reserved for later coding-quality suites.

## API integration

List cases:

```text
GET /evals/cases
```

Run a suite or case id:

```json
POST /evals/run
{
  "suite": "payload_recovery",
  "repo_path": "/home/obsidian/Elevate_test",
  "safe_only": true
}
```

The `/evals/run` endpoint first looks for matching declarative cases by `suite` or `id`; if found, it executes them with `evals.case_loader`.

## Case example

```json
{
  "id": "payload_recovery",
  "suite": "payload_recovery",
  "type": "regression",
  "title": "Dispatcher missing payload recovery",
  "safe_only": true,
  "runner": "payload_recovery",
  "repo_path_default": "/home/obsidian/Elevate_test",
  "steps": [
    {
      "endpoint": "/coding/repo/action",
      "body": {"action": "instructions", "payload": {}},
      "expect": {"status": 400, "error_code": "missing_payload_fields"}
    }
  ],
  "score": {
    "missing_payload_detected": 30,
    "example_payload_present": 30,
    "corrected_retry_succeeds": 40
  }
}
```

## Phase 4 acceptance criteria

Phase 4 is complete when:

```text
case directory exists
at least 5 initial case files exist
case files load successfully
cases are listed by /evals/cases
executable cases run locally
executable cases run through /evals/run
reports are generated for runs
```

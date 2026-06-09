# Coding GPT Evaluation API — Phase 3 Complete

Phase 3 exposes safe evaluation endpoints for reviewing Coding GPT and backend performance.

## Auth

All `/evals/*` endpoints require `x-api-key`. Coding or operator keys are accepted.

## Endpoints

### `GET /evals/cases`

Lists built-in eval cases and regression files.

### `POST /evals/run`

Runs a safe evaluation suite.

```json
{
  "suite": "core_smoke",
  "repo_path": "/home/obsidian/Elevate_test",
  "safe_only": true
}
```

Supported suites:

- `core_smoke`
- `payload_recovery`
- `release_gate`

The core smoke suite calls the safe smoke-test workflow and does not commit, push, create PRs, install dependencies, or modify the primary checkout.

### `POST /evals/report`

Generates or reads an evaluation report.

```json
{
  "report_id": "phase3_core_smoke"
}
```

### `POST /evals/compare`

Compares two reports or run ids.

```json
{
  "current_report_id": "phase3_payload_recovery",
  "baseline_report_id": "phase3_core_smoke"
}
```

### `GET /evals/regressions`

Lists regression records under `evals/regressions/`.

### `POST /evals/regressions`

Creates a regression record safely under `evals/regressions/`.

```json
{
  "id": "missing_dispatcher_payload_20260609",
  "title": "Missing dispatcher payload regression",
  "failure_layer": "custom_gpt_behavior",
  "symptom": "GPT called dispatcher with action only and no payload.",
  "expected_behavior": "Retry once using error.example_payload.",
  "source": "real_custom_gpt_run",
  "details": {}
}
```

## Validation

Phase 3 was validated with:

```bash
python manual_phase3_evals_test.py
```

Expected result:

```json
{
  "total": 7,
  "passed": 7,
  "failed": 0
}
```

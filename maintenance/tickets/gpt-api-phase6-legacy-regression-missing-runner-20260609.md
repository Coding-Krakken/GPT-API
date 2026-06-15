---
id: gpt-api-phase6-legacy-regression-missing-runner-20260609
status: open
severity: low
area: maintenance
created: 2026-06-15
resolved:
---

# Phase 6 regression runner failure: legacy regression missing runner

## Issue
The new Phase 6 permanent regression suite ran 7 regression files and passed 6/7. The legacy file `evals/regressions/phase3_manual_test_regression.yaml` was created during Phase 3 as a static regression record and does not include an executable `runner` field.

## Command
```bash
cd /root/GPT-API && python evals/run_regressions.py --repo-path /home/obsidian/Elevate_test --run-id phase6_manual_regressions
```

## Result
```json
{
  "status": 400,
  "total": 7,
  "passed": 6,
  "failed": 1,
  "error": {
    "code": "unsupported_regression_runner",
    "message": "Unsupported runner: None"
  },
  "id": "phase3_manual_test_regression"
}
```

## Impact
Phase 6 runner correctly detected that all regression records must be executable. The legacy Phase 3 record needs a `runner: "phase3_regression_create"` field.

## Fix
Update `evals/regressions/phase3_manual_test_regression.yaml` with `runner: "phase3_regression_create"`, then rerun the regression suite.

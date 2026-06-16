---
id: "gpt-api-phase5-runner-import-error-20260609"
status: "resolved"
severity: "medium"
area: "patch-safety"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified release gate and eval-oriented tests pass."
---

# Phase 5 eval runner import path error

## Issue
Running `python evals/run_eval_suite.py --list` from the repo failed because Python set `sys.path[0]` to `/root/GPT-API/evals`, so the top-level `evals` package was not importable as `evals`.

## Error
```text
ModuleNotFoundError: No module named 'evals'
```

## Command
```bash
cd /root/GPT-API && python evals/run_eval_suite.py --list
```

## Fix
Patch `evals/run_eval_suite.py` to insert the repository root into `sys.path` before importing `evals.*` modules.

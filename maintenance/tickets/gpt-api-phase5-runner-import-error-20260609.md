---
id: gpt-api-phase5-runner-import-error-20260609
status: open
severity: low
area: maintenance
created: 2026-06-15
resolved:
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

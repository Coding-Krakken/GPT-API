---
id: gpt-api-phase7-command-too-long-20260609
status: open
severity: medium
area: tooling
created: 2026-06-15
resolved:
---

# Phase 7 command too long

## Issue
While implementing Phase 7 backend engine metrics, a Python patch command for `evals/scoring.py` and `evals/report.py` exceeded the control API command-length limit.

## Error
```json
{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."}
```

## Attempted action
Patch scoring/report modules to import `evals.engine_metrics`, include engine metrics/scores in backend scoring, and render engine metrics in Markdown reports.

## Next step
Apply the edits using smaller commands or direct file rewrites.

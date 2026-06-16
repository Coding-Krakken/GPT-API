---
id: "gpt-api-phase5-command-too-long-20260609"
status: "obsolete"
severity: "low"
area: "patch-safety"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Phase 5 implementation command too long

## Issue
While implementing Phase 5 evaluation suites, a shell command that patched `evals/case_loader.py` exceeded the control API command length limit.

## Error
```json
{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."}
```

## Intended action
Patch `evals/case_loader.py` to add:
- suite membership support via `suites`
- `repo_intelligence` runner
- `simple_bugfix` executable fixture runner
- dispatch support for the new runners

## Resolution plan
Write the patch logic to a temporary Python script and run that script from the repo instead of sending a very long shell command.

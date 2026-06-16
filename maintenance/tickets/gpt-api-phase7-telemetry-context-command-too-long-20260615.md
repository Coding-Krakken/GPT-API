---
id: "gpt-api-phase7-telemetry-context-command-too-long-20260615"
status: "open"
severity: "medium"
area: "tooling"
created: "2026-06-16"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Use script-file edits instead of oversized inline shell patches."
verification_result: "not_run"
resolution_summary: "Command-length blocker encountered during Phase 7 telemetry context implementation."
---

# Maintainer Ticket: Phase 7 telemetry context patch exceeded shell command length

## Issue
While fully implementing Phase 7 backend engine metrics, an inline shell/Python patch command exceeded the `/shell` 4096-character limit.

## Intended work
- Add telemetry context support to `utils/eval_telemetry.py`.
- Stamp eval suite/case nested events with `run_id`, `suite`, `case_id`, `repo_path`, and `runner`.
- Scope Phase 7 engine metric reports by run id.
- Return engine score data from eval suite CLI output.

## Observed error

```json
{"error":{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)"},"status":400}
```

## Workaround
Write a patch script under `/tmp` with the file API and execute it with a short shell command.

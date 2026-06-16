---
id: "gpt-api-phase1-quality-telemetry-gap-20260609"
status: "resolved"
severity: "medium"
area: "patch-safety"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified current release gate and telemetry/phase suites pass."
---

# Phase 1 telemetry validation gap: quality_run missing for dispatcher path

## Issue
Phase 1 validation ran both smoke tests successfully, but telemetry validation expected at least one `quality_run` event and found none.

## Commands
```bash
cd /root/GPT-API
EVAL_TELEMETRY_ROOT=/tmp/gpt-api-phase1-telemetry-test python manual_elevate_smoke_endpoint_test.py
EVAL_TELEMETRY_ROOT=/tmp/gpt-api-phase1-telemetry-test python manual_elevate_core_endpoint_test.py
```

## Result
Endpoint tests passed:

```text
smoke endpoint: 18/18 passed
manual core endpoint test: 18/18 passed
```

Telemetry event counts included dispatcher and subprocess events, but no `quality_run` event.

## Root cause
`quality_run` was logged in `/agent/coding-task/submit` when `run_quality=true`, but the smoke tests call quality through `/coding/quality/action`, whose internal `check()` function only returned results and did not emit `quality_run`.

## Fix
Emit `quality_run` from the quality dispatcher engine/check path in `routes/coding_dispatch.py`.

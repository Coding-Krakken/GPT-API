---
id: gpt-api-phase1-quality-telemetry-gap-20260609
status: open
severity: low
area: endpoint
created: 2026-06-15
resolved:
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

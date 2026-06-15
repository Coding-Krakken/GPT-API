---
id: gpt-api-production8000-phase13-http-hang-20260609
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# Production `/evals/phase13/run` HTTP call hangs on port 8000

## Issue
During production-mode testing against the restarted service on port 8000, the HTTP endpoint `/evals/phase13/run` did not return within the 160-second polling window.

## What passed first
With `require_clean_git=false`:

```text
PASS phase13_status_no_git_gate http=200 body_status=200 elapsed_ms=218.67
PASS release_gate_no_git_gate http=200 body_status=200 elapsed_ms=2015.57
```

## Hanging call
```text
POST /evals/phase13/run
payload:
{
  "repo_path": "/home/obsidian/Elevate_test",
  "run_id": "prod8000_no_git_phase13",
  "promote_baseline": false,
  "create_bundle": false,
  "require_clean_git": false
}
```

The incremental report remained at:

```text
stage: started_phase13_no_git_gate
```

## Impact
Most production endpoints are healthy, but the Phase 13 HTTP endpoint itself needs investigation. The Phase 13 CLI had previously completed successfully, so this appears specific to running Phase 13 through the production HTTP route.

## Next step
Stop the hanging test client, inspect process/connections/logs, and consider adding internal timeout/async offloading to `/evals/phase13/run` or returning an immediately persisted run artifact rather than blocking the HTTP request.

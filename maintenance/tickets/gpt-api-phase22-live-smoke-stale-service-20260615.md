---
id: "gpt-api-phase22-live-smoke-stale-service-20260615"
status: "needs_verification"
severity: "high"
area: "deployment"
created: "2026-06-15"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Run deployment verification against localhost and ngrok after service restart."
verification_result: "not_run"
resolution_summary: "Requires live deployment/tunnel verification against the currently running service and Custom GPT Action schema."
---

# Maintainer Ticket: Phase 22 live smoke failed because running service appears stale

## Issue
After implementing Phase 21/22 docs and smoke verification in `/root/GPT-API`, the in-process smoke matrix and release gate passed, but a live smoke check against the already-running service at `http://127.0.0.1:8000` failed on `/health`.

## Command

```bash
cd /root/GPT-API
set -a && . ./.env 2>/dev/null && set +a
API_KEY="${API_KEY:-${OPERATOR_GPT_API_KEY:-}}" BASE_URL=http://127.0.0.1:8000 python3 scripts/smoke_local.py --live
```

## Error

```text
smoke verification failed: /health: expected one of [200], got 404
```

## Assessment
The checked-out code now contains `/health`, `/healthz`, and `/api/health`, and the in-process smoke matrix passes. The live failure indicates the running process on port 8000 is stale or is serving a different code version.

## Next action
Restart the service after explicit maintainer approval, then rerun:

```bash
BASE_URL=http://127.0.0.1:8000 API_KEY=[REDACTED] python3 scripts/smoke_local.py --live
```

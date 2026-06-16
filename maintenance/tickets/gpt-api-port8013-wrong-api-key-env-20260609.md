---
id: "gpt-api-port8013-wrong-api-key-env-20260609"
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

# Port 8013 backend started with temporary API key instead of repo .env key

## Issue
The isolated backend instance on port 8013 was started with inline environment variables:

```text
API_KEY=manual-port8013-key
OPERATOR_GPT_API_KEY=manual-port8013-key
CODING_GPT_API_KEY=manual-port8013-key
```

This overrode the repository `.env` file. As a result, the backend accepted the temporary manual key but rejected the actual `.env` `API_KEY`.

## Evidence
Auth smoke test against `http://127.0.0.1:8013/evals/phase13/status?require_clean_git=false`:

```text
temporary_manual http 200 body_status 200
env_API_KEY http 403 {"detail":"Invalid API key for route"}
```

Process environment for PID listening on 8013 showed `API_KEY`, `OPERATOR_GPT_API_KEY`, and `CODING_GPT_API_KEY` were set from inline values, not sourced from `.env`.

## Impact
Manual endpoint tests on port 8013 were valid for endpoint behavior but not valid for verifying the real `.env` API key configuration.

## Fix
Restart the isolated 8013 backend after sourcing `/root/GPT-API/.env`, without overriding API keys inline, then rerun auth and affected endpoint tests using the `.env` key.

---
id: gpt-api-prod8000-smoke-direct-control-error-20260610
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# Production smoke direct command interrupted control channel

## Issue
Running `python evals/http_smoke.py --base-url http://127.0.0.1:8000 ...` directly through the control shell caused the control channel to return an aiohttp `ClientResponseError`.

## Likely cause
The command was served by the same production backend process being smoke-tested, so synchronous local HTTP calls from inside the shell route can interrupt/block the control response.

## Fix approach
Run the HTTP smoke tester as a detached background process and poll the incremental report file from a separate control call.

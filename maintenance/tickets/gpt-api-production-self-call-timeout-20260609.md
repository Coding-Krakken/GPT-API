---
id: gpt-api-production-self-call-timeout-20260609
status: open
severity: high
area: schema
created: 2026-06-15
resolved:
---

# Production local self-call timeout during in-process tool request

## Issue
While testing the restarted production service on port 8000, HTTP calls to `http://127.0.0.1:8000/...` timed out when launched from `runShellCommand`.

## Observed commands
The command inspected listeners/processes and then tried local HTTP calls to:

```text
http://127.0.0.1:8000/coding-gpt-core-openapi.yaml
http://127.0.0.1:8000/evals/phase13/status?require_clean_git=true
```

Both timed out from within that same tool request.

## Likely cause
The tool request itself is served by the same production GPT-API process on port 8000. The synchronous shell route can block the server event loop while it waits for nested HTTP calls back into the same process, causing self-call deadlock/timeouts.

## Impact
This does not prove production endpoints are down. It means local self-calls must be run by an external/background tester process after the shell route returns, or tested through a separate backend instance.

## Next step
Launch an external background test script that sleeps briefly, then calls production endpoints on port 8000 after the tool request has returned. Read the generated report afterward.

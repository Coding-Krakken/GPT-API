---
id: "gpt-api-debug-routes-pipe-inspection-failed-20260615"
status: "obsolete"
severity: "low"
area: "deployment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Maintainer Ticket: Debug route subset inspection pipe failed

## Issue
While reviewing GPT Action output and comparing route availability between ports 8000 and 18088, a shell pipeline intended to parse `/debug/routes` failed with `curl: Failed writing body` and Python JSON parse errors.

## Attempted action
The command piped `curl -sS http://127.0.0.1:<port>/debug/routes` into an inline Python script to filter routes.

## Observed output

```text
curl: Failed writing body
Expecting value: line 1 column 1 (char 0)
```

## Context
The failure was limited to the diagnostic pipeline. Earlier direct endpoint checks succeeded and established the important finding: port 8000 is serving a stale backend without `/health`, `/healthz`, `/api/health`, `/metrics`, or slashless aliases, while port 18088 serves the current backend with those routes.

## Workaround
Use separate file output or a simple shell/Python command without here-doc stdin conflicts when parsing route JSON.

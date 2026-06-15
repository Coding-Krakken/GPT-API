---
id: gpt-api-debug-routes-pipe-inspection-failed-20260615
status: open
severity: low
area: endpoint
created: 2026-06-15
resolved:
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

---
id: "gpt-api-main-patch-literal-corruption-20260614"
status: "open"
severity: "high"
area: "patch-safety"
created: "2026-06-15"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Run malformed patch, secret-path, preview/apply parity, and literal-corruption regression tests."
verification_result: "not_run"
resolution_summary: "Patch engine historical corruption requires stronger adversarial regression coverage."
---

# Maintainer Ticket: manageFiles patch wrote literal patch text into main.py

## Issue
While implementing GPT-API Phases 4-7 in `/root/GPT-API`, the `manageFiles` endpoint with action `patch` replaced `/root/GPT-API/main.py` with the literal unified patch text instead of applying the patch.

## Attempted action
Endpoint/tool: `manageFiles`

Payload shape:
```json
{
  "action": "patch",
  "path": "/root/GPT-API/main.py",
  "patch": "*** Begin Patch\n*** Update File: /root/GPT-API/main.py\n@@\n-from fastapi.responses import PlainTextResponse\n+from fastapi.responses import JSONResponse, PlainTextResponse\n..."
}
```

## Observed result
The tool returned status 200 and message `patch completed`, but reading `/root/GPT-API/main.py` showed the file contents were only the literal patch block:

```text
*** Begin Patch
*** Update File: /root/GPT-API/main.py
@@
-from fastapi.responses import PlainTextResponse
+from fastapi.responses import JSONResponse, PlainTextResponse
...
*** End Patch
```

## Impact
`main.py` became syntactically invalid until restored. This would break service import/startup and tests.

## Workaround
Restore `main.py` from git or rewrite it from the previously-read known-good content, then avoid `manageFiles` patch for this change. Use a direct file write or a shell/python editing script instead.

## Repository context
Repo: `/root/GPT-API`
Branch: `feature/coding-gpt-safe-agent`
Task: implement Phases 4-7 (health routes, route normalization/method alignment, typed endpoint availability, structured `/api/*` handling).

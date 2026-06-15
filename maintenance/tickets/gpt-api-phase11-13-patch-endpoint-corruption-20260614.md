---
id: gpt-api-phase11-13-patch-endpoint-corruption-20260614
status: open
severity: medium
area: schema
created: 2026-06-15
resolved:
---

# GPT-API Phase 11-13 patch endpoint corrupted target files

## Issue
The file patch endpoint was used with a standard unified patch for `run_gpt_service.sh` and later `routes/dispatch.py`. In both cases, instead of applying the patch cleanly, the endpoint replaced the target file content with the patch text. The issue was detected immediately and both files were restored/repaired.

## Attempted patch shape
```text
*** Begin Patch
*** Update File: /root/GPT-API/routes/dispatch.py
@@
-@router.post("/", dependencies=[Depends(verify_key)])
+@router.post("", dependencies=[Depends(verify_key)])
+@router.post("/", dependencies=[Depends(verify_key)], include_in_schema=False)
 async def dispatch_to_agent(...)
*** End Patch
```

## Impact
Temporary file corruption during implementation. Fixed by restoring `routes/dispatch.py` from Git and using Python text replacement. `run_gpt_service.sh` was rewritten from intended content.

## Workaround
Avoid manageFiles `patch` for now. Use direct full-file writes or controlled Python text replacements.

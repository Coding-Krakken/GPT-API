---
id: "gpt-api-phase11-13-patch-endpoint-corruption-20260614"
status: "resolved"
severity: "high"
area: "patch-safety"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "this-commit"
verification_command: "pytest -q tests/test_patch_safety_phase5.py tests/test_coding_safety_boundaries.py tests/test_coding_workflow_guards.py"
verification_result: "passed"
resolution_summary: "Phase 5 added adversarial patch safety coverage for malformed patch blocks, secret paths, preview/apply parity, and no-mutation guarantees."
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

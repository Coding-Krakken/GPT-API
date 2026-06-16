---
id: "gpt-api-report-print-pipe-error-20260609"
status: "obsolete"
severity: "low"
area: "maintenance"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Report print pipeline error after successful endpoint test

## Issue
After `manual_elevate_core_endpoint_test.py` successfully completed with 18/18 endpoints passed, a follow-up shell pipeline intended to pretty-print failed items used a heredoc in a way that consumed stdin before `json.load(sys.stdin)`.

## Command shape
```bash
python manual_elevate_core_endpoint_test.py && cat /tmp/gpt-api-elevate-core-endpoint-report.json | python - <<'PY'
import json,sys
r=json.load(sys.stdin)
...
PY
```

## Error
```text
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

## Impact
No impact on endpoint testing. The endpoint test had already passed and wrote `/tmp/gpt-api-elevate-core-endpoint-report.json` successfully. The report was subsequently read directly via the file API.

## Correct approach
Read the report directly with a normal Python file open or file API, not `cat | python - << heredoc`.

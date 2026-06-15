---
id: gpt-api-report-print-pipe-error-20260609
status: open
severity: low
area: endpoint
created: 2026-06-15
resolved:
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

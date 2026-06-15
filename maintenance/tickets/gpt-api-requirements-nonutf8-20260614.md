---
id: gpt-api-requirements-nonutf8-20260614
status: open
severity: low
area: schema
created: 2026-06-15
resolved:
---

# GPT-API requirements.txt non-UTF/binary read failure

## Issue
Attempting to read `/root/GPT-API/requirements.txt` through the file interface failed because byte 0 is not valid UTF-8.

## Attempted action
```json
{"action":"read","path":"/root/GPT-API/requirements.txt"}
```

## Error
```json
{"code":"internal_error","message":"'utf-8' codec can't decode byte 0xff in position 0: invalid start byte"}
```

## Impact
Phase 13 dependency declaration cannot safely update `requirements.txt` without first determining whether the file is corrupted, binary, UTF-16, or intentionally encoded differently.

## Workaround
Implement OpenAPI validation using dependencies already available in the environment where possible, and avoid modifying `requirements.txt` until encoding is clarified.

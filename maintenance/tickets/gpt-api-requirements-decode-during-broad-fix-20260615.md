---
id: "gpt-api-requirements-decode-during-broad-fix-20260615"
status: "open"
severity: "high"
area: "tool-output"
created: "2026-06-16"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Run bounded log/read tests against binary/non-UTF8 and large outputs."
verification_result: "not_run"
resolution_summary: "Encoding/output-size robustness remains actionable for logs and file inspection."
---

# Maintainer Ticket: requirements inspection hit UTF-8 decode error during broad hardening

## Issue
While investigating the missing `requests` test dependency, a shell command that printed `requirements.txt` failed with a UTF-8 decode error.

## Command

```bash
cd /root/GPT-API && grep -n '^requests' requirements.txt requirements-gui-linux.txt 2>/dev/null || true && sed -n '1,80p' requirements.txt && sed -n '1,220p' tests/test_api.py
```

## Error

```text
'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```

## Context
There is already a related maintainer ticket for non-UTF/binary `requirements.txt`. Continue with binary-safe inspection and repair.

---
id: "gpt-api-phase14-17-inspection-decode-error-20260614"
status: "open"
severity: "high"
area: "tool-output"
created: "2026-06-15"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Run bounded log/read tests against binary/non-UTF8 and large outputs."
verification_result: "not_run"
resolution_summary: "Encoding/output-size robustness remains actionable for logs and file inspection."
---

# GPT-API Phase 14-17 inspection decode error

## Issue
While implementing Phases 14-17 in `/root/GPT-API`, a combined file-inspection command failed because the tool response encountered non-UTF-8/binary bytes.

## Attempted command
```bash
cd /root/GPT-API && sed -n '1,220p' main.py && echo '--- audit ---' && sed -n '1,240p' utils/audit.py && echo '--- tests conf ---' && sed -n '1,220p' tests/conftest.py && echo '--- current scripts ---' && find scripts -maxdepth 2 -type f -print -exec sed -n '1,160p' {} \;
```

## Error
```text
'utf-8' codec can't decode byte 0x8b in position 18436: invalid start byte
```

## Context
Task: continue on current branch, commit and push all changes, fully implement Phases 14-17.

## Workaround
Use targeted text-only reads and skip binary/generated files.

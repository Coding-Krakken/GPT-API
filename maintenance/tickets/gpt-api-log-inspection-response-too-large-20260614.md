---
id: "gpt-api-log-inspection-response-too-large-20260614"
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

# GPT-API log inspection blocked by ResponseTooLargeError

## Issue
While evaluating `/root/GPT-API` service logs and endpoint performance, a combined shell command that printed file sizes, process state, listening ports, and tails of several logs failed with `ResponseTooLargeError`.

## Attempted command
```bash
cd /root/GPT-API && echo '--- file sizes ---' && ls -lh audit.log logs/*.log 2>/dev/null && echo '--- service processes ---' && ps -eo pid,etime,pcpu,pmem,args | grep -E 'uvicorn|fastapi|main.py|run_gpt_service|ngrok' | grep -v grep || true && echo '--- listening ports ---' && (ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null || true) | grep -E ':(8000|8013|4040|5000|8080)\\b|python|uvicorn|ngrok' || true && echo '--- recent audit ---' && tail -n 120 audit.log && echo '--- recent gpt-cli ---' && tail -n 160 logs/gpt-cli.log && echo '--- recent ngrok ---' && tail -n 80 logs/ngrok.log
```

## Tool error
`ResponseTooLargeError`

## Context
Repository: `/root/GPT-API`
Task: inspect logs, evaluate service/endpoints, and review maintainer tickets.

## Workaround
Continue with smaller, targeted commands and bounded log excerpts.

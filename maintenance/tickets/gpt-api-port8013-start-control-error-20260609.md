---
id: "gpt-api-port8013-start-control-error-20260609"
status: "obsolete"
severity: "low"
area: "deployment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Port 8013 backend start control-layer error

## Issue
While starting a separate GPT-API backend instance on port 8013 for final endpoint testing, the control tool returned an aiohttp `ClientResponseError`.

## Command attempted
```bash
cd /root/GPT-API && rm -f /tmp/gpt-api-port8013.log /tmp/gpt-api-port8013.pid && API_HOST=127.0.0.1 API_PORT=8013 API_KEY=manual-port8013-key OPERATOR_GPT_API_KEY=manual-port8013-key CODING_GPT_API_KEY=manual-port8013-key REPO_ALLOWED_ROOTS=/home/obsidian,/tmp,/root WORKTREE_ROOT=/tmp/gpt-api-port8013-worktrees TASK_LEDGER_ROOT=/tmp/gpt-api-port8013-worktrees/.gpt-api-tasks nohup python cli.py >/tmp/gpt-api-port8013.log 2>&1 & echo $! >/tmp/gpt-api-port8013.pid && sleep 2 && cat /tmp/gpt-api-port8013.pid && curl -sS -m 5 -i http://127.0.0.1:8013/coding-gpt-core-openapi.yaml | head -20 && echo '== log ==' && tail -40 /tmp/gpt-api-port8013.log
```

## Error
```text
ClientResponseError
Encountered exception: <class 'aiohttp.client_exceptions.ClientResponseError'>
```

## Next step
Check whether the background process actually started, inspect `/tmp/gpt-api-port8013.log` and `/tmp/gpt-api-port8013.pid`, then continue manual endpoint testing if the separate server is live.

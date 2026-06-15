# Coding GPT Knowledge: Typed Endpoint Reference

Dispatcher endpoints are deprecated for Custom GPT usage.

Use typed endpoints directly.

Examples:

POST /repo/instructions
{ "repo_path": "/path/to/repo" }

POST /repo/relevant-context
{ "repo_path": "/path/to/repo", "task": "Improve coverage" }

POST /repo/search
{ "repo_path": "/path/to/repo", "query": "coverage" }

POST /repo/read-context
{ "repo_path": "/path/to/repo", "files": ["package.json"] }

POST /test/discover
{ "workspace_path": "/tmp/workspace" }

POST /test/run
{ "workspace_path": "/tmp/workspace", "command_name": "npm test" }

No payload wrapper is required or expected.

## Related current contracts

Dispatcher endpoints remain deprecated for Custom GPT usage. When testing typed endpoints, remember the current backend contracts: protected endpoints require `x-api-key`; dangerous operations require `confirm: true` or a supported `confirmation` string; health routes `/health`, `/healthz`, and `/api/health` are unauthenticated; and patch preview rejects blocked paths with `blocked_patch_path`.

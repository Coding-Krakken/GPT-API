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
# Coding GPT Knowledge: Troubleshooting

## Repository context

Repository inspection uses typed repo endpoints. If context is needed, call /repo/instructions, /repo/relevant-context, /repo/search, /repo/read-context, /repo/symbols, or /repo/test-map.

Do not claim repository access is blocked because dispatcher payloads are unavailable.

## 403

Verify x-api-key configuration.

## Quality failures

A quality endpoint can succeed while repository checks fail. Inspect the returned output and continue the workflow.

## Coverage tasks

Generate a measured baseline before modifying thresholds. Required artifacts:
- coverage_baseline
- coverage_report
- coverage_gaps

## Confirmation required

If a response body contains `confirmation_required`, do not retry blindly. Ask for or verify explicit user approval, then include `confirm: true` or a supported `confirmation` string in the same operation payload. For `/batch`, the confirmation must be inside the nested payload or rollback payload that performs the dangerous action.

## Health and slash behavior

Use unauthenticated `GET /health`, `GET /healthz`, and `GET /api/health` to distinguish a running backend from an authentication or schema problem. Slashless core action endpoints should not 307 redirect. Duplicate slashes are normalized; a duplicate-slash request should return the canonical endpoint response, not a 404.

## Patch policy failures

`blocked_patch_path` means the diff touches a protected path such as `.env`, secrets, credentials, an unsafe absolute path, or a traversal path. `invalid_unified_diff` means the patch is malformed or wrapped in prose/Markdown fences. Do not bypass these errors with shell, broad file, or unrestricted git endpoints.

## Interactive validation blockers

If lint/build/test output contains an interactive prompt, do not report it as a code failure. Mark the check as blocked tooling/configuration with `status: blocked_interactive`. For Next.js `next lint` setup prompts, recommend adding explicit ESLint config and using `eslint . --max-warnings=0` in CI.

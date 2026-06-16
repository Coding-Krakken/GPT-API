# Phase 21-22 Documentation and Verification

This runbook keeps GPT-API documentation, schemas, and operational verification aligned.

## Phase 21: documentation contract

Every maintainer-facing change must update the relevant docs in the same branch as the code change.

### Canonical service URLs

Use base URLs without trailing slashes so client path joins never produce duplicate slashes:

```text
http://127.0.0.1:8000
https://unscrutinized-immotile-jermaine.ngrok-free.dev
```

Schema files must also use non-trailing-slash server URLs:

```yaml
servers:
  - url: https://unscrutinized-immotile-jermaine.ngrok-free.dev
```

### Authentication

All protected endpoints require an `x-api-key` header. Role-specific keys are supported:

```text
OPERATOR_GPT_API_KEY  broad operator routes
CODING_GPT_API_KEY    coding-agent routes
COS_GPT_API_KEY       dispatch routes
API_KEY               legacy fallback/operator key
```

Never paste API keys into normal chat or docs. Use placeholders such as `[REDACTED]`.

### Slash policy

Core action endpoints must support both slashless and trailing-slash forms without a redirect:

```text
/shell and /shell/
/files and /files/
/git and /git/
/monitor and /monitor/
/dispatch and /dispatch/
/package and /package/
```

Duplicate path slashes are normalized by middleware so `//agent/coding-task` and `/agent//coding-task` are treated as canonical paths.

### Health endpoints

The main API on port 8000 exposes unauthenticated lightweight health checks:

```text
GET /health
GET /healthz
GET /api/health
```

Use authenticated diagnostics for deeper state:

```text
GET /metrics
GET /diagnostics/*
```

### Safe endpoint usage

Prefer structured endpoints over long shell commands:

```text
/files      read/write/patch/list/stat files
/code       run/test/lint/format code with validation
/git        repository operations
/package    dependency operations with policy confirmation
/batch      grouped endpoint calls
/script     larger temporary scripts when a shell command would exceed limits
```

Dangerous operations require explicit confirmation. See `docs/PHASE18_20_OPERATIONS.md` and `config/policy.yaml`.

### Long-job workflow

HTTP requests should not be used for indefinite work. Use background/task workflows for long-running operations and poll task status/logs rather than holding a request open.

### Maintainer ticket workflow

Maintainer tickets are tracked under `maintenance/tickets/` and summarized by:

```bash
python3 scripts/ticket_index.py
```

When a blocker occurs, capture the command, error, logs, environment context, and next suggested action in a Markdown ticket. Mark duplicates instead of creating parallel untracked narratives.

### Documentation checklist

Before merge, verify the docs describe:

```text
canonical base URLs
required auth header and role keys
slash and duplicate-slash behavior
health endpoints
safe endpoint usage and dangerous-operation confirmation
long-job/background workflow
ticket workflow
release gate and schema validation
```

## Phase 22: final verification matrix

Run the verification matrix before declaring a branch ready.

### Fast local matrix

This matrix does not require a running external service. It uses FastAPI's in-process test client:

```bash
python3 scripts/smoke_local.py
```

It verifies:

```text
health endpoints return 200
OpenAPI YAML is served
schema server URLs have no trailing slash
core slashless endpoints do not redirect
duplicate slashes do not produce 404s
protected endpoints enforce auth
representative typed coding endpoints are present
metrics endpoint is available without auth and also responds with auth
```

### Live matrix against a running service

Use this when the service is already running on port 8000:

```bash
BASE_URL=http://127.0.0.1:8000 API_KEY=[REDACTED] python3 scripts/smoke_local.py --live
```


### Deployment verification matrix

Phase 3 deployment verification is handled by:

```bash
python3 scripts/verify_deployment.py
```

The default mode runs in-process checks plus static schema checks and writes a JSON and Markdown deployment verification report under `/tmp/gpt-api-deployment-reports`. Use it before live rollout to confirm local route, schema, and ticket-era regression expectations.

For a running local service, use:

```bash
BASE_URL=http://127.0.0.1:8000 API_KEY=<redacted> python3 scripts/verify_deployment.py --live
```

For the public ngrok-backed Action endpoint, use:

```bash
PUBLIC_BASE_URL=https://unscrutinized-immotile-jermaine.ngrok-free.dev API_KEY=<redacted> python3 scripts/verify_deployment.py --public
```

For release/deploy sign-off, combine live and public checks and pin the expected commit:

```bash
EXPECT_COMMIT=$(git rev-parse --short HEAD) API_KEY=<redacted> python3 scripts/verify_deployment.py --live --public --expect-commit "$EXPECT_COMMIT"
```

The verifier checks health endpoints, metrics, served OpenAPI files, required Coding GPT Action paths, route presence for typed agent/env endpoints, local Git state, and schema import guard constraints.

### Full release gate

Run:

```bash
./scripts/release_gate.sh
```

The release gate checks:

```text
clean git worktree unless ALLOW_DIRTY=true
ticket index generation
OpenAPI validation
deployment verification report generation
Phase 14-17 focused contract tests
Phase 21-22 smoke verification
```

Use `ALLOW_DIRTY=true ./scripts/release_gate.sh` only while developing local changes. Never use that override for final release signoff.

### Manual spot checks

For live debugging, these commands should produce the expected outcomes:

```bash
BASE=http://127.0.0.1:8000
KEY="$API_KEY"

curl -sS "$BASE/health"
curl -sS "$BASE/healthz"
curl -sS "$BASE/openapi.yaml" >/tmp/openapi.yaml
curl -sS -H "x-api-key: $KEY" "$BASE/system/"
curl -sS -H "x-api-key: $KEY" -X POST "$BASE/monitor/" -H 'Content-Type: application/json' -d '{"type":"cpu"}'
```

No-redirect check:

```bash
for p in shell files git monitor dispatch package; do
  curl -sS -o /dev/null -w "$p %{http_code} %{redirect_url}\n" \
    -X POST "$BASE/$p" \
    -H "x-api-key: $KEY" \
    -H "Content-Type: application/json" \
    -d '{}'
done
```

Duplicate-slash check:

```bash
curl -i -X POST "$BASE//agent/coding-task" \
  -H "x-api-key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected result: validation or auth response, not `404`.

### Pass/fail rule

A branch is not ready if any of these are true:

```text
a documented endpoint returns 404
core slashless action endpoints return 307
schema server URLs end with /
health routes are missing on port 8000
OpenAPI validation fails
a release-gate test fails
git status contains undocumented generated artifacts
```

# Maintainer Ticket Resolution Plan

Last updated: 2026-06-15
Branch: `feature/coding-gpt-safe-agent`

This plan covers the unresolved maintainer tickets that were encountered while strengthening and testing the affected GPT-API endpoints and OpenAPI contract. Resolved local cleanup tickets were removed from `/tmp` after verification.

## Cleanup completed

- Removed local untracked backup file: `openapi.yaml.bak.20260614_210756`.
- Removed resolved dependency/validator tickets:
  - `/tmp/full_pytest_missing_requests_1781487110.md`
  - `/tmp/openapi_validator_missing_1781485840.md`

## Remaining tickets in scope

### 1. `/tmp/full_pytest_patch_preview_env_safety_1781487137.md`

**Problem**

The full test suite fails because `/patch/preview` accepts a patch creating or modifying `.env`. The existing test expects a structured rejection with status 400.

**Implementation plan**

1. Inspect the `/patch/preview` route and any shared patch safety utilities.
2. Identify how patch file paths are parsed from unified diffs.
3. Add a denylist check for sensitive paths, including at minimum:
   - `.env`
   - `.env.*`
   - `*.pem`
   - `*.key`
   - private key paths
   - credential/config files already blocked elsewhere in the repo
4. Ensure both `a/path` and `b/path` sides of a diff are checked.
5. Ensure paths are normalized before evaluation so bypasses such as `./.env` or nested traversal are rejected.
6. Return the existing structured error shape with HTTP 400 / body status 400.
7. Add or update tests for:
   - creating `.env`
   - modifying `.env`
   - deleting `.env`
   - path traversal toward `.env`
   - allowed safe patch preview
8. Run the full suite:

```bash
PYTHONPATH=/root/GPT-API python -m pytest -q tests --maxfail=1
```

**Acceptance criteria**

- The failing safety-boundary test passes.
- Safe patch previews still work.
- Full suite progresses past this blocker.

### 2. `/tmp/runShellCommand_unrecognized_timeout_seconds_1781486425.md`

**Problem**

The external `runShellCommand` tool rejected a `timeout_seconds` argument even though timeout control is useful and the runtime `/shell` route supports timeout semantics.

**Implementation plan**

1. Inspect the tool schema / action adapter that exposes `runShellCommand`.
2. Decide whether the tool should accept `timeout_seconds` as an alias for its supported timeout field or whether documentation should explicitly forbid it.
3. Prefer backwards-compatible support:
   - accept `timeout_seconds`
   - map it to the tool's internal timeout control
   - preserve the current supported timeout field
4. Add tests for:
   - `timeout_seconds` accepted
   - legacy timeout field still accepted
   - conflicting timeout values handled predictably
5. Update OpenAPI/tool documentation if needed.

**Acceptance criteria**

- Calls with `timeout_seconds` no longer raise `UnrecognizedKwargsError`.
- Existing timeout behavior remains compatible.

### 3. `/tmp/pytest_main_import_failure_1781486437.md`

**Problem**

Raw `pytest -q tests --maxfail=1` failed to import `main`, while `PYTHONPATH=/root/GPT-API python -m pytest ...` worked.

**Implementation plan**

1. Reproduce from `/root/GPT-API` with plain `pytest -q tests --maxfail=1`.
2. Inspect pytest configuration files, package layout, and invocation environment.
3. Add a stable project-level pytest config if missing:
   - `pythonpath = .` in `pytest.ini` or equivalent supported config
4. Confirm that direct `pytest` and `python -m pytest` both import `main` successfully.
5. Avoid test changes that rely on global environment variables outside the repo.

**Acceptance criteria**

- `pytest -q tests --maxfail=1` imports `main` without needing manual `PYTHONPATH`.
- Existing focused endpoint tests still pass.

### 4. `/tmp/code_concurrency_patch_command_too_long_1781486642.md`

**Problem**

A large inline shell patch command exceeded the 4096-character command limit while modifying `/code` concurrency behavior.

**Implementation plan**

1. Treat this as a tooling ergonomics issue rather than an endpoint runtime bug.
2. Provide a first-class safe workflow for large edits:
   - write large content through `/files`
   - run short commands through `/shell`
   - optionally document this pattern in a developer guide
3. Consider adding a helper script or Make target for applying generated patch files from `/tmp`.
4. Add documentation warning that `/shell.command` is intentionally capped at 4096 characters.

**Acceptance criteria**

- Developers have documented, supported steps for large patches.
- No endpoint security limits are weakened.

### 5. `/tmp/endpoint_probe_command_length_limit_20260614.md`

**Problem**

A large manual endpoint probe harness could not be created via one heredoc shell command because of the same 4096-character command limit.

**Implementation plan**

1. Reuse the large-edit workflow from ticket 4.
2. Commit a reusable manual probe template or document the `/files`-then-`/shell` approach.
3. Add a short example showing how to create `/tmp/manual_endpoint_probe.py` via the structured file endpoint.

**Acceptance criteria**

- Manual testers have a documented safe way to create large probes.
- The `/shell` command limit remains intact.

### 6. `/tmp/openapi_patch_command_too_long_1781485733.md`

**Problem**

A large inline OpenAPI patch script exceeded the `/shell` command limit.

**Implementation plan**

1. Reuse the documented large-edit workflow from tickets 4 and 5.
2. Add an OpenAPI-specific example:
   - write a Python patch script to `/tmp` via `/files`
   - run `python /tmp/script.py` via `/shell`
   - validate with `openapi_spec_validator`
3. Optionally add a repo script for routine OpenAPI validation.

**Acceptance criteria**

- Large OpenAPI modifications have a documented safe workflow.
- OpenAPI validation remains part of the workflow.

### 7. `/tmp/openapi_python_permission_1781485780.md`

**Problem**

The private Python sandbox cannot read `/root/GPT-API/openapi.yaml`, while repo-control endpoints can. This is an environment isolation limitation.

**Implementation plan**

1. Document that repo files under `/root/GPT-API` should be accessed through repository-control endpoints or commands run from inside the repo.
2. Avoid relying on the private Python sandbox for `/root`-owned repo files.
3. If sandbox access is desired, evaluate whether a safe read-only bind mount or permission adjustment is appropriate.
4. Do not loosen permissions broadly without a security review.

**Acceptance criteria**

- Maintainers understand the supported access pattern.
- No unsafe permission changes are made.

## Recommended execution order

1. Fix `/patch/preview` sensitive-path validation because it blocks the full test suite.
2. Add stable pytest import configuration for plain `pytest` runs.
3. Add documentation/helper workflow for large edits and OpenAPI patching.
4. Decide whether to extend the external `runShellCommand` tool schema with `timeout_seconds` compatibility.
5. Review sandbox permission policy separately with security considerations.

## Validation checklist after implementation

Run:

```bash
cd /root/GPT-API
python - <<'PY'
import yaml
from pathlib import Path
from openapi_spec_validator import validate
validate(yaml.safe_load(Path('openapi.yaml').read_text()))
print('openapi validation passed')
PY
PYTHONPATH=/root/GPT-API python -m pytest -q tests --maxfail=1
pytest -q tests --maxfail=1
```

Expected:

- OpenAPI validation passes.
- Full suite passes or reaches only newly discovered blockers with new tickets filed.
- Plain `pytest` imports `main` successfully.

## Phase 2 completion: codeOps test-mode robustness

Implemented after the initial ticket lifecycle triage. The `/code` endpoint now resolves the active codeOps tickets by supporting:

- language inference for Python test files and pytest repository roots;
- repo-root pytest execution without extension mismatch errors;
- `PYTHONPATH` injection from `working_dir` so project imports and `conftest.py` imports work;
- safe multi-file pytest selectors through `argv` and safe legacy `args`;
- structured `validationResult` metadata for `/code` test runs.

Resolved ticket IDs:

- `gpt-api-codeops-pytest-import-path-20260614`
- `gpt-api-codeops-test-language-required-20260614`
- `gpt-api-phase14-17-codeops-language-required-20260614`
- `gpt-api-phase18-20-codeops-multipath-test-20260615`
- `gpt-api-phase21-22-codeops-pytest-args-rejected-20260615`

Verification:

```bash
pytest -q tests/test_code_phase2.py tests/test_code.py tests/test_code_api_hardening.py tests/test_code_content_edge_cases.py tests/test_expanded_endpoint_contract.py tests/test_phase15_release_gate.py
```

Result: `50 passed, 1 warning`.

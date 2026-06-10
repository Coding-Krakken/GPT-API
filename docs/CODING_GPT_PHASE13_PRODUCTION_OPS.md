# Coding GPT Phase 13: Production Operations

Phase 13 turns the evaluation system into an operational ship/no-ship workflow for a copilot-like Coding GPT.

## Purpose

Phase 13 verifies that the Coding GPT system is ready to ship, promotes good baselines, and creates portable release/evaluation bundles. It sits on top of Phase 12's continuous learning loop.

## Capabilities

- Operational readiness checks
- Continuous-learning release cycle
- Baseline comparison
- Optional approved-baseline promotion
- Portable release bundle generation
- Ship/no-ship decision with blockers and warnings
- API endpoints and CLI entrypoint

## CLI

```bash
python evals/phase13_ops.py --repo-path /home/obsidian/Elevate_test
```

Development mode, allowing uncommitted local changes:

```bash
python evals/phase13_ops.py --repo-path /home/obsidian/Elevate_test --allow-dirty
```

Promote a passing run as the latest approved runtime baseline:

```bash
python evals/phase13_ops.py --repo-path /home/obsidian/Elevate_test --promote
```

## API

Readiness:

```text
GET /evals/phase13/status
```

Run full Phase 13 cycle:

```text
POST /evals/phase13/run
```

Payload:

```json
{
  "repo_path": "/home/obsidian/Elevate_test",
  "promote_baseline": false,
  "create_bundle": true,
  "require_clean_git": true
}
```

Promote a report manually:

```text
POST /evals/phase13/promote-baseline
```

Payload:

```json
{
  "report_id": "release_gate_...",
  "reason": "approved after review"
}
```

## Ship-ready criteria

A Phase 13 run is ship-ready only when:

- Continuous-learning release gate passes
- Operational readiness passes
- Known real failures have regression coverage
- Schema is under the Custom GPT operation limit
- Instructions are under the Custom GPT character/byte limit
- Auth and server URL are correct
- Core smoke and regression suites pass
- Git is clean and pushed when `require_clean_git` is true
- Baseline comparison shows no unacceptable regression

## Artifacts

Phase 13 writes runtime artifacts under:

```text
/tmp/gpt-api-evals/phase13/
/tmp/gpt-api-evals/baselines/
```

A release bundle includes:

- core and full schemas
- short GPT instructions
- knowledge files
- evaluation docs
- latest report artifacts
- manifest with git state

## Operating rule

Do not ship a Coding GPT backend/schema/instruction change unless Phase 13 is complete and ship-ready, or a human explicitly accepts and documents the tradeoff.

## Production-safe HTTP behavior

`POST /evals/phase13/run` is job-based by default. It returns quickly with `status: 202` and a `run_id` instead of blocking the production HTTP worker until the entire Phase 13 cycle finishes.

Poll job status with:

```text
GET /evals/phase13/job/{run_id}
```

To force legacy synchronous behavior, set `blocking: true` in the request. This is intended for local or controlled tests only.

## Incremental production smoke testing

Use the incremental HTTP smoke tester for production validation:

```bash
python evals/http_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --repo-path /home/obsidian/Elevate_test \
  --run-id prod_smoke
```

The tester writes a JSON report after every endpoint call, so partial results are preserved even if an endpoint hangs or the test process is interrupted.

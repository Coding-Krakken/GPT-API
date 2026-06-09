# Coding GPT Phase 9: Baselines and Release Gates

Phase 9 adds a deterministic release gate for Coding GPT backend, schema, instructions, knowledge files, eval suites, and regressions.

## Command

```bash
python evals/run_release_gate.py --repo-path /home/obsidian/Elevate_test
```

While developing the gate itself, use:

```bash
python evals/run_release_gate.py --repo-path /home/obsidian/Elevate_test --allow-dirty
```

`--allow-dirty` skips clean/pushed git checks only so the gate can be validated before committing the gate implementation.

## API endpoint

```text
POST /evals/release-gate
```

Example body:

```json
{
  "repo_path": "/home/obsidian/Elevate_test",
  "require_clean_git": true
}
```

## Gate checks

The release gate fails on any blocker:

- Git worktree is clean before gate.
- Local HEAD matches `origin/feature/coding-gpt-safe-agent`.
- `coding-gpt-core-openapi.yaml` exists.
- `coding-openapi.yaml` exists.
- Core schema has at most 30 operations.
- Core schema server is `https://unscrutinized-immotile-jermaine.ngrok-free.dev`.
- Old `https://gpt-api.ngrok.app` domain is absent.
- `ApiKeyAuth` is configured as header `x-api-key`.
- Security requirements use `- ApiKeyAuth: []`.
- `/agent/coding-task/smoke-test` is present.
- Dispatcher payload-required hint is present.
- Forbidden operator paths/markers are absent from core schema.
- `coding-gpt-instructions.md` is under 8000 chars and bytes.
- Required knowledge files exist.
- Python route/util modules compile.
- Declarative `release_gate` suite passes.
- Permanent regression suite passes.

Warnings are included for readiness scores below target, but they do not block release unless converted into blockers later.

## Reports

Each run writes:

```text
/tmp/gpt-api-evals/release_gates/<run_id>.json
/tmp/gpt-api-evals/release_gates/<run_id>.md
/tmp/gpt-api-evals/reports/<run_id>.json
/tmp/gpt-api-evals/reports/<run_id>.md
```

The release-gate report contains pass/fail checks. The eval report contains telemetry-derived agent/backend scores, failures, and recommendations.

## Release rule

Do not ship Coding GPT schema, instruction, knowledge, or backend changes unless:

```text
python evals/run_release_gate.py --repo-path /home/obsidian/Elevate_test
```

returns exit code 0.

# Coding GPT Phase 5: Core Evaluation Suites

Phase 5 implements executable, repeatable evaluation suites for the Coding GPT backend and Custom GPT readiness layer.

## Status

Phase 5 is complete when these suites exist, run, and pass against `/home/obsidian/Elevate_test`:

- `core_smoke`
- `payload_discipline`
- `policy_safety`
- `repo_intelligence`
- `coding_task_quality`
- `phase5_full`
- `release_gate`

## Runner

Use:

```bash
python evals/run_eval_suite.py --suite phase5_full --repo-path /home/obsidian/Elevate_test
```

List cases:

```bash
python evals/run_eval_suite.py --list
```

## Suites

### core_smoke

Runs the safe one-call core smoke test. It verifies the uploadable core workflow and dispatcher endpoints.

Expected: 18/18 core checks pass, no primary checkout modifications, no commits, no pushes, no PRs, no installs.

### payload_discipline

Validates the previous real-world failure mode where a dispatcher was called without required payload fields.

Expected: `missing_payload_fields` is returned with `example_payload`, and the corrected retry succeeds.

### policy_safety

Verifies policy blocks sensitive paths such as `.env`.

Expected: policy endpoint responds and secret path is blocked.

### repo_intelligence

Verifies safe read-only repository intelligence helpers:

- overview
- instructions
- relevant_context
- test_map
- route_map

Expected: repo is detected, language is detected, and all context tools respond successfully.

### coding_task_quality

Creates a temporary fixture Git repo with a one-line bug, creates an isolated worktree, previews/applies the expected patch through the safe patch engine, and validates quality response.

Expected: fixture workspace created, patch preview applies, patch applies, only one file changes, quality endpoint responds.

### phase5_full

Runs all Phase 5 cases:

- core smoke
- repo environment quality structure
- final answer contract
- payload discipline
- policy safety
- repo intelligence
- coding task quality

Expected: 7/7 cases pass.

### release_gate

Runs the subset that should block release if failing:

- core smoke
- final answer contract
- payload discipline
- policy safety
- repo intelligence

Expected: 5/5 cases pass.

## Latest validation

Validated against `/home/obsidian/Elevate_test`:

```text
core_smoke: 1/1 passed
payload_discipline: 1/1 passed
policy_safety: 1/1 passed
repo_intelligence: 1/1 passed
coding_task_quality: 1/1 passed
phase5_full: 7/7 passed
release_gate: 5/5 passed
```

Generated reports were written under:

```text
/tmp/gpt-api-evals/reports/
```

Named reports from validation:

```text
phase5_core_smoke
phase5_payload_discipline
phase5_policy_safety
phase5_repo_intelligence
phase5_coding_task_quality
phase5_full
phase5_release_gate
```

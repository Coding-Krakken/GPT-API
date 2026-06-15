---
id: gpt-api-phase11-release-gate-cli-flag-20260609
status: open
severity: medium
area: release
created: 2026-06-15
resolved:
---

# Phase 11 release gate CLI flag mismatch

## Issue
Attempted to rerun the release gate with `--no-require-clean-git`, but the CLI supports `--allow-dirty` instead.

## Command
```bash
python evals/run_release_gate.py --repo-path /home/obsidian/Elevate_test --run-id phase11_dashboard_validation_inprogress --no-require-clean-git
```

## Error
```text
usage: run_release_gate.py [-h] [--repo-path REPO_PATH] [--run-id RUN_ID] [--allow-dirty]
run_release_gate.py: error: unrecognized arguments: --no-require-clean-git
```

## Next step
Rerun with `--allow-dirty` for in-progress validation, then commit and rerun without `--allow-dirty` once clean.

---
id: "gpt-api-phase11-release-gate-cli-flag-20260609"
status: "obsolete"
severity: "low"
area: "maintenance"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
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

# Coding GPT Knowledge: Evaluation System

The backend includes an evaluation system for reviewing and improving the Coding GPT and backend engines.

## Key endpoints

- `/evals/run` runs a suite or case.
- `/evals/release-gate` runs schema, instruction, regression, and smoke checks.
- `/evals/continuous-learning` runs the Phase 12 improvement loop and returns a ship/no-ship decision.
- `/evals/dashboard` shows recent reports.
- `/evals/ingest-debug-log` parses Custom GPT Actions debug transcripts.

## Phase 12 continuous learning loop

Use `/evals/continuous-learning` before shipping improvements. It runs the release gate, checks known regression coverage, compares against a baseline/latest report, checks git cleanliness/pushed state when requested, and writes JSON/Markdown reports.

Example:

```json
{
  "repo_path": "/home/obsidian/Elevate_test",
  "require_clean_git": true
}
```

A result is ship-ready only when the release gate passes, known failures have regressions, git is clean/pushed when required, and the baseline comparison does not show unacceptable regressions.

## Rule

Every real failure should become a regression case. Every claimed improvement should have before/after evaluation evidence.

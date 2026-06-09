# Coding GPT Knowledge: Dispatcher Reference

All dispatcher calls require `payload`. Never call a dispatcher with only `{ "action": "..." }`.

Use either:

```json
{
  "category": "repo",
  "action": "overview",
  "payload": {"repo_path":"/home/obsidian/Elevate_test"}
}
```

or category-specific endpoints:

```json
{
  "action": "overview",
  "payload": {"repo_path":"/home/obsidian/Elevate_test"}
}
```

## Categories and actions

repo: `overview`, `search`, `read_context`, `symbols`, `instructions`, `dependency_graph`, `test_map`, `relevant_context`, `callgraph`, `references`, `symbol_references`, `route_map`, `changed_context`, `recent_history_context`

workspace: `create`, `status`, `diff`, `destroy`, `commit`, `pr_create`, `diff_summary`, `risk_report`, `review_checklist`

patch: `preview`, `apply`, `revert`, `apply_recorded`, `history`, `revert_recorded`, `validate_risk`

test: `discover`, `run`

quality: `check`

diagnostics: `parse`, `suggest_context`, `triage`

policy: `check`, `evaluate_action`, `evaluate_action_deep`

tasks: `create`, `update`, `read`, `list`, `cancel`, `lock`, `claim`, `unlock`, `log`, `artifacts`, `resume`, `status_summary`, `gc`, `lock_ttl`, `artifact_index`, `validate_artifacts`, `phase_contract`, `iteration_summary`

github: `issue_read`, `pr_read`, `checks_read`, `pr_comment`, `pr_create_from_task`, `checks_diagnose`, `pr_apply_feedback_plan`, `pr_update_body`, `pr_review_comments`, `checks_logs`, `branch_push`, `checks_repair_plan`, `pr_feedback_to_patch_contract`

env: `discover`, `doctor`, `prepare_dry_run`, `prepare_approved`

## Required payload examples

Repo instructions:

```json
{"action":"instructions","payload":{"repo_path":"/home/obsidian/Elevate_test"}}
```

Relevant context:

```json
{"action":"relevant_context","payload":{"repo_path":"/home/obsidian/Elevate_test","task":"Fix the bug"}}
```

Workspace status:

```json
{"action":"status","payload":{"workspace_path":"/tmp/gpt-api-worktrees/<workspace>"}}
```

Test discovery:

```json
{"action":"discover","payload":{"workspace_path":"/tmp/gpt-api-worktrees/<workspace>"}}
```

Task artifact index:

```json
{"action":"artifact_index","payload":{"task_id":"task_..."}}
```

If the backend returns `missing_payload_fields`, use `error.example_payload` and retry once.

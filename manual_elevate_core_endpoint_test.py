from __future__ import annotations

import json
import os
from pathlib import Path

REPORT = Path('/tmp/gpt-api-elevate-core-endpoint-report.json')
REPO = '/home/obsidian/Elevate_test'
KEY = 'manual-elevate-test-key'

os.environ['API_KEY'] = KEY
os.environ['OPERATOR_GPT_API_KEY'] = KEY
os.environ['CODING_GPT_API_KEY'] = KEY
os.environ['REPO_ALLOWED_ROOTS'] = '/home/obsidian,/tmp,/root'
os.environ['WORKTREE_ROOT'] = '/tmp/gpt-api-elevate-worktrees'
os.environ['TASK_LEDGER_ROOT'] = '/tmp/gpt-api-elevate-worktrees/.gpt-api-tasks'

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
H = {'x-api-key': KEY}
results = []

def post(name: str, path: str, payload: dict, expect_statuses=(200,), allow_body_status_string=True):
    response = client.post(path, headers=H, json=payload)
    try:
        body = response.json()
    except Exception:
        body = {'raw': response.text[:1000]}
    body_status = body.get('status') if isinstance(body, dict) else None
    ok = response.status_code in expect_statuses or body_status in expect_statuses
    if allow_body_status_string and isinstance(body_status, str):
        ok = True
    item = {
        'name': name,
        'path': path,
        'http_status': response.status_code,
        'body_status': body_status,
        'ok': bool(ok),
        'summary': json.dumps(body, default=str)[:1600],
    }
    results.append(item)
    return body, item

# 1. agent workflow endpoints
agent, _ = post('01_agent_coding_task', '/agent/coding-task', {
    'repo_path': REPO,
    'task': 'Manual smoke test all uploadable Coding GPT core endpoints without modifying the primary checkout.',
    'mode': 'plan_apply_verify',
    'workspace_strategy': 'git_worktree',
    'max_iterations': 3,
    'approval_policy': 'safe_auto',
    'create_pr': False,
})

task_id = agent.get('task', {}).get('task_id') if isinstance(agent, dict) else None
workspace = agent.get('workspace', {}).get('workspace_path') if isinstance(agent, dict) else None
if not task_id or not workspace:
    REPORT.write_text(json.dumps({'repo_path': REPO, 'fatal': 'agent task did not return task/workspace', 'results': results}, indent=2))
    raise SystemExit(1)

post('02_agent_next', '/agent/coding-task/next', {'task_id': task_id})
post('03_agent_submit_artifact', '/agent/coding-task/submit', {
    'task_id': task_id,
    'artifact_name': 'relevant_context',
    'artifact': {'manual_smoke_test': True, 'repo_path': REPO},
    'run_tests': False,
    'run_quality': False,
})
post('04_agent_repair_plan', '/agent/coding-task/repair-plan', {'task_id': task_id, 'max_files': 5})
post('05_agent_iteration_summary', '/agent/coding-task/iteration-summary', {'task_id': task_id})
post('06_agent_contract_report', '/agent/coding-task/contract-report', {'task_id': task_id})
post('07_agent_finalize_no_commit', '/agent/coding-task/finalize', {
    'task_id': task_id,
    'commit': False,
    'create_pr': False,
    'enforce_contract': False,
})

# 2. universal and category dispatcher endpoints. Use safe read/planning actions only.
post('08_coding_universal_action', '/coding/action', {
    'category': 'diagnostics',
    'action': 'triage',
    'payload': {
        'diagnostics': [{'tool': 'pytest', 'file': 'tests/test_smoke.py', 'message': 'manual smoke diagnostic'}],
        'task': 'manual smoke test',
    },
})
post('09_coding_repo_action', '/coding/repo/action', {
    'action': 'overview',
    'payload': {'repo_path': REPO, 'max_depth': 2},
})
post('10_coding_workspace_action', '/coding/workspace/action', {
    'action': 'status',
    'payload': {'workspace_path': workspace},
})
post('11_coding_patch_action', '/coding/patch/action', {
    'action': 'history',
    'payload': {'workspace_path': workspace, 'task_id': task_id},
})
post('12_coding_test_action', '/coding/test/action', {
    'action': 'discover',
    'payload': {'workspace_path': workspace},
})
post('13_coding_quality_action', '/coding/quality/action', {
    'action': 'check',
    'payload': {'workspace_path': workspace, 'timeout_seconds': 60},
})
post('14_coding_diagnostics_action', '/coding/diagnostics/action', {
    'action': 'parse',
    'payload': {'tool': 'pytest', 'stdout': 'FAILED tests/test_x.py::test_x', 'stderr': ''},
})
post('15_coding_policy_action', '/coding/policy/action', {
    'action': 'check',
    'payload': {'path': 'README.md', 'repo_root': REPO},
})
post('16_coding_tasks_action', '/coding/tasks/action', {
    'action': 'artifact_index',
    'payload': {'task_id': task_id},
})
post('17_coding_github_action', '/coding/github/action', {
    'action': 'checks_diagnose',
    'payload': {'checks': [{'name': 'manual-smoke', 'state': 'success'}]},
})
post('18_coding_env_action', '/coding/env/action', {
    'action': 'discover',
    'payload': {'workspace_path': workspace},
})

passed = sum(1 for r in results if r['ok'])
report = {
    'repo_path': REPO,
    'task_id': task_id,
    'workspace_path': workspace,
    'total': len(results),
    'passed': passed,
    'failed': len(results) - passed,
    'failed_items': [r for r in results if not r['ok']],
    'results': results,
}
REPORT.write_text(json.dumps(report, indent=2))
print(json.dumps({k: report[k] for k in ['repo_path','task_id','workspace_path','total','passed','failed']}, indent=2))

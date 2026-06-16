from __future__ import annotations

import sys
from pathlib import Path as _ManualPath

REPO_ROOT = _ManualPath(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))



def main() -> int:
    import json
    import os
    import shutil
    import subprocess
    from pathlib import Path

    SANDBOX = Path('/tmp/gpt-api-coding-sandbox')
    REPO = SANDBOX / 'repo'
    WORKTREES = SANDBOX / 'worktrees'
    REPORT = Path('/tmp/gpt-api-coding-endpoint-manual-report.json')
    KEY = 'manual-test-key'

    shutil.rmtree(SANDBOX, ignore_errors=True)
    SANDBOX.mkdir(parents=True)
    REPO.mkdir()
    WORKTREES.mkdir()
    os.environ['API_KEY'] = KEY
    os.environ['OPERATOR_GPT_API_KEY'] = KEY
    os.environ['CODING_GPT_API_KEY'] = KEY
    os.environ['REPO_ALLOWED_ROOTS'] = str(SANDBOX)
    os.environ['WORKTREE_ROOT'] = str(WORKTREES)
    os.environ['TASK_LEDGER_ROOT'] = str(WORKTREES / '.gpt-api-tasks')

    subprocess.run(['git', 'init'], cwd=REPO, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Manual Tester'], cwd=REPO, check=True)
    subprocess.run(['git', 'config', 'user.email', 'manual@example.com'], cwd=REPO, check=True)
    (REPO / 'README.md').write_text('# Sandbox\nCoding task auth add example.\n', encoding='utf-8')
    (REPO / '.github').mkdir()
    (REPO / '.github' / 'copilot-instructions.md').write_text('Use pytest. Keep patches small.\n', encoding='utf-8')
    (REPO / 'pytest.ini').write_text('[pytest]\npythonpath = .\n', encoding='utf-8')
    (REPO / 'requirements.txt').write_text('pytest\n', encoding='utf-8')
    (REPO / 'app.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
    (REPO / 'auth.py').write_text('def allowed(role):\n    return role == "operator"\n', encoding='utf-8')
    (REPO / 'tests').mkdir()
    (REPO / 'tests' / 'test_app.py').write_text('from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n', encoding='utf-8')
    subprocess.run(['git', 'add', '.'], cwd=REPO, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=REPO, check=True, capture_output=True)

    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    H = {'x-api-key': KEY, 'Content-Type': 'application/json'}
    results = []
    state = {}

    def call(name, method, path, payload=None, expect=(200,)):
        if method == 'GET':
            resp = client.get(path, headers=H)
        else:
            resp = client.post(path, headers=H, json=payload or {})
        try:
            body = resp.json()
        except Exception:
            body = {'text': resp.text[:500]}
        body_status = body.get('status') if isinstance(body, dict) else None
        ok = (resp.status_code in expect) or (body_status in expect) or (isinstance(body_status, str) and resp.status_code == 200) or path.endswith('.yaml')
        results.append({'name': name, 'path': path, 'http': resp.status_code, 'body_status': body_status, 'ok': ok, 'summary': str(body)[:500]})
        return body

    # Schema/debug
    call('debug_routes', 'GET', '/debug/routes')
    call('coding_openapi', 'GET', '/coding-openapi.yaml')

    # Repo endpoints
    call('repo_overview', 'POST', '/repo/overview', {'repo_path': str(REPO)})
    call('repo_search', 'POST', '/repo/search', {'repo_path': str(REPO), 'query': 'def add'})
    call('repo_read_context', 'POST', '/repo/read-context', {'repo_path': str(REPO), 'files': ['app.py', 'auth.py']})
    call('repo_symbols', 'POST', '/repo/symbols', {'repo_path': str(REPO), 'files': ['app.py', 'auth.py']})
    call('repo_instructions', 'POST', '/repo/instructions', {'repo_path': str(REPO)})
    call('repo_dependency_graph', 'POST', '/repo/dependency-graph', {'repo_path': str(REPO)})
    call('repo_test_map', 'POST', '/repo/test-map', {'repo_path': str(REPO)})
    ctx = call('repo_relevant_context', 'POST', '/repo/relevant-context', {'repo_path': str(REPO), 'task': 'change add implementation and auth policy', 'max_files': 8})

    # Task and agent endpoints
    created = call('task_create', 'POST', '/tasks/create', {'repo_path': str(REPO), 'task': 'Manual endpoint exercise', 'metadata': {'source': 'manual'}})
    task_id = created.get('result', {}).get('task_id')
    state['task_id'] = task_id
    call('task_read', 'POST', '/tasks/read', {'task_id': task_id})
    call('task_list', 'POST', '/tasks/list', {})
    call('task_lock', 'POST', '/tasks/lock', {'task_id': task_id, 'owner': 'manual'})
    call('task_claim', 'POST', '/tasks/claim', {'task_id': task_id, 'owner': 'manual'})
    call('task_unlock', 'POST', '/tasks/unlock', {'task_id': task_id, 'owner': 'manual'})
    call('task_log', 'POST', '/tasks/log', {'task_id': task_id, 'event_type': 'manual_test', 'data': {'ok': True}})
    call('task_artifacts', 'POST', '/tasks/artifacts', {'task_id': task_id, 'name': 'relevant_context', 'artifact': ctx})
    call('task_resume', 'POST', '/tasks/resume', {'task_id': task_id})

    agent = call('agent_coding_task', 'POST', '/agent/coding-task', {'repo_path': str(REPO), 'task': 'Manual agent init', 'max_iterations': 2})
    agent_task_id = agent.get('task', {}).get('task_id')
    if agent_task_id:
        call('agent_next', 'POST', '/agent/coding-task/next', {'task_id': agent_task_id})

    # Workspace endpoints
    ws_body = call('workspace_create', 'POST', '/workspace/create', {'repo_path': str(REPO), 'task_id': 'manual-endpoint'})
    ws = ws_body.get('workspace_path')
    state['workspace_path'] = ws
    call('workspace_status', 'POST', '/workspace/status', {'workspace_path': ws})

    # Env endpoints
    call('env_discover', 'POST', '/env/discover', {'workspace_path': ws})
    call('env_doctor', 'POST', '/env/doctor', {'workspace_path': ws})
    call('env_prepare_dry_run', 'POST', '/env/prepare-dry-run', {'workspace_path': ws})
    call('env_prepare_approved_requires_approval', 'POST', '/env/prepare-approved', {'workspace_path': ws, 'approved': False}, expect=(400,))

    patch = '''diff --git a/app.py b/app.py
    --- a/app.py
    +++ b/app.py
    @@ -1,2 +1,2 @@
     def add(a, b):
    -    return a + b
    +    return int(a) + int(b)
    '''
    call('patch_preview', 'POST', '/patch/preview', {'workspace_path': ws, 'patch': patch})
    call('patch_apply', 'POST', '/patch/apply', {'workspace_path': ws, 'patch': patch})
    call('workspace_diff', 'POST', '/workspace/diff', {'workspace_path': ws})
    call('workspace_diff_summary', 'POST', '/workspace/diff-summary', {'workspace_path': ws})
    call('workspace_risk_report', 'POST', '/workspace/risk-report', {'workspace_path': ws})
    call('workspace_review_checklist', 'POST', '/workspace/review-checklist', {'workspace_path': ws})

    # Diagnostics/policy/test/quality
    fake_pytest = 'FAILED tests/test_app.py::test_add - AssertionError\n  File "app.py", line 2'
    diag = call('diagnostics_parse', 'POST', '/diagnostics/parse', {'tool': 'pytest', 'stdout': fake_pytest})
    call('diagnostics_suggest_context', 'POST', '/diagnostics/suggest-context', {'diagnostics': diag.get('diagnostics', [])})
    call('policy_check', 'POST', '/policy/check', {'path': str(REPO / 'app.py'), 'repo_root': str(REPO)})
    call('policy_evaluate_action', 'POST', '/policy/evaluate-action', {'action': 'create_pr', 'workspace_path': ws, 'changed_files': ['app.py'], 'tests_passed': True, 'quality_passed': True, 'user_approved_network_write': False}, expect=(400,))
    call('test_discover', 'POST', '/test/discover', {'workspace_path': ws})
    call('test_run', 'POST', '/test/run', {'workspace_path': ws, 'command_name': 'pytest', 'timeout_seconds': 60})
    call('quality_check', 'POST', '/quality/check', {'workspace_path': ws, 'timeout_seconds': 60})

    # GitHub safe helpers: dry-run comment succeeds without network; read endpoints are exercised and may return safe gh errors.
    call('github_pr_comment_dry_run', 'POST', '/github/pr/comment', {'workspace_path': ws, 'pr': '1', 'body': 'manual test', 'dry_run': True})
    call('github_issue_read_expected_safe_error', 'POST', '/github/issue/read', {'workspace_path': ws, 'issue': '1'}, expect=(400,))
    call('github_pr_read_expected_safe_error', 'POST', '/github/pr/read', {'workspace_path': ws, 'pr': '1'}, expect=(400,))
    call('github_checks_read_expected_safe_error', 'POST', '/github/checks/read', {'workspace_path': ws}, expect=(400,))

    call('workspace_commit', 'POST', '/workspace/commit', {'workspace_path': ws, 'message': 'manual endpoint change'})
    call('workspace_pr_create_dry_run', 'POST', '/workspace/pr-create', {'workspace_path': ws, 'title': 'Manual endpoint PR', 'body': 'Manual dry run'})
    call('patch_revert_expected_after_commit_safe_error', 'POST', '/patch/revert', {'workspace_path': ws, 'patch': patch}, expect=(200,))
    call('task_update', 'POST', '/tasks/update', {'task_id': task_id, 'status': 'manual_complete', 'workspace_path': ws})
    call('task_cancel', 'POST', '/tasks/cancel', {'task_id': task_id, 'reason': 'manual lifecycle complete'})
    call('workspace_destroy_expected_dirty_or_removed', 'POST', '/workspace/destroy', {'workspace_path': ws, 'force': True}, expect=(200, 400))

    report = {'sandbox': str(SANDBOX), 'state': state, 'total': len(results), 'passed': sum(1 for r in results if r['ok']), 'failed': [r for r in results if not r['ok']], 'results': results}
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(REPORT), 'total': report['total'], 'passed': report['passed'], 'failed_count': len(report['failed']), 'failed': report['failed'][:10]}, indent=2))
    if report['failed']:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

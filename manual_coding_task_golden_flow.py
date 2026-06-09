from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

SANDBOX = Path('/tmp/gpt-api-coding-golden')
REPO = SANDBOX / 'repo'
WORKTREES = SANDBOX / 'worktrees'
REPORT = Path('/tmp/gpt-api-coding-golden-report.json')
KEY = 'golden-key'

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
subprocess.run(['git', 'config', 'user.name', 'Golden Tester'], cwd=REPO, check=True)
subprocess.run(['git', 'config', 'user.email', 'golden@example.com'], cwd=REPO, check=True)
(REPO / '.github').mkdir()
(REPO / '.github' / 'copilot-instructions.md').write_text('Use pytest. Keep changes minimal.\n', encoding='utf-8')
(REPO / 'pytest.ini').write_text('[pytest]\npythonpath = .\n', encoding='utf-8')
(REPO / 'requirements.txt').write_text('pytest\n', encoding='utf-8')
(REPO / 'mathlib.py').write_text('def add(a, b):\n    return str(a) + str(b)\n', encoding='utf-8')
(REPO / 'tests').mkdir()
(REPO / 'tests' / 'test_mathlib.py').write_text('from mathlib import add\n\ndef test_add_numbers():\n    assert add(1, 2) == 3\n', encoding='utf-8')
subprocess.run(['git', 'add', '.'], cwd=REPO, check=True)
subprocess.run(['git', 'commit', '-m', 'init broken mathlib'], cwd=REPO, check=True, capture_output=True)

from fastapi.testclient import TestClient
from main import app
client = TestClient(app)
H = {'x-api-key': KEY, 'Content-Type': 'application/json'}
steps = []

def post(name, path, payload, ok_status=(200,)):
    resp = client.post(path, headers=H, json=payload)
    body = resp.json()
    body_status = body.get('status') if isinstance(body, dict) else None
    ok = resp.status_code in ok_status or body_status in ok_status or isinstance(body_status, str)
    steps.append({'name': name, 'path': path, 'http': resp.status_code, 'body_status': body_status, 'ok': ok, 'summary': str(body)[:700]})
    if not ok:
        raise AssertionError(f'{name} failed: {body}')
    return body

agent = post('agent_init', '/agent/coding-task', {'repo_path': str(REPO), 'task': 'Fix add so numeric addition returns numbers', 'max_iterations': 3})
task_id = agent['task']['task_id']
workspace = agent['workspace']['workspace_path']
post('next_after_init', '/agent/coding-task/next', {'task_id': task_id})
instructions = post('repo_instructions', '/repo/instructions', {'repo_path': str(REPO)})
context = post('relevant_context', '/repo/relevant-context', {'repo_path': str(REPO), 'task': 'Fix add so numeric addition returns numbers', 'max_files': 6})
post('submit_context', '/agent/coding-task/submit', {'task_id': task_id, 'artifact_name': 'relevant_context', 'artifact': {'instructions': instructions, 'context': context}})
post('next_need_patch', '/agent/coding-task/next', {'task_id': task_id})
patch = '''diff --git a/mathlib.py b/mathlib.py
--- a/mathlib.py
+++ b/mathlib.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return str(a) + str(b)
+    return a + b
'''
submit = post('submit_patch_tests_quality', '/agent/coding-task/submit', {'task_id': task_id, 'patch': patch, 'run_tests': True, 'run_quality': True})
assert submit['results']['patch']['applied'] is True
assert submit['results']['tests']['passed'] is True
assert submit['results']['quality']['passed'] is True
post('next_review_or_finalize', '/agent/coding-task/next', {'task_id': task_id})
finalized = post('finalize_commit_pr_dry_run', '/agent/coding-task/finalize', {'task_id': task_id, 'commit': True, 'commit_message': 'Fix numeric addition', 'create_pr': True, 'pr_title': 'Fix numeric addition', 'pr_body': 'Golden dry-run PR', 'user_approved_network_write': False})
assert finalized['final_report']['summary']['has_tests'] is True
assert finalized['final_report']['summary']['has_quality'] is True
post('github_pr_from_task_dry_run', '/github/pr/create-from-task', {'workspace_path': workspace, 'task_id': task_id, 'dry_run': True})
post('patch_history', '/patch/history', {'workspace_path': workspace, 'task_id': task_id})
status = post('workspace_status', '/workspace/status', {'workspace_path': workspace})
# .gpt-api metadata remains untracked internally; code commit should be clean except metadata.
post('checks_diagnose', '/github/checks/diagnose', {'checks': [{'name': 'ci', 'state': 'success'}, {'name': 'lint', 'state': 'failure'}]})

report = {'sandbox': str(SANDBOX), 'repo': str(REPO), 'workspace': workspace, 'task_id': task_id, 'steps': steps, 'total': len(steps), 'passed': sum(1 for s in steps if s['ok']), 'failed': [s for s in steps if not s['ok']], 'finalized': finalized, 'workspace_status': status}
REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'report': str(REPORT), 'task_id': task_id, 'workspace': workspace, 'total': report['total'], 'passed': report['passed'], 'failed': len(report['failed'])}, indent=2))

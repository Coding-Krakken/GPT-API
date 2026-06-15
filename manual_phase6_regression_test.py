from __future__ import annotations

import json
import os
from pathlib import Path

os.environ['API_KEY'] = 'manual-phase6-test-key'
os.environ['OPERATOR_GPT_API_KEY'] = 'manual-phase6-test-key'
os.environ['CODING_GPT_API_KEY'] = 'manual-phase6-test-key'
os.environ['REPO_ALLOWED_ROOTS'] = '/home/obsidian,/tmp,/root'
os.environ['WORKTREE_ROOT'] = '/tmp/gpt-api-phase6-worktrees'
os.environ['TASK_LEDGER_ROOT'] = '/tmp/gpt-api-phase6-worktrees/.gpt-api-tasks'

from fastapi.testclient import TestClient
from main import app

REPORT = Path('/tmp/gpt-api-phase6-regression-api-report.json')
client = TestClient(app)
headers = {'x-api-key': 'manual-phase6-test-key'}
results = []

def check(name: str, ok: bool, details: dict):
    results.append({'name': name, 'ok': bool(ok), 'details': details})

list_resp = client.get('/evals/regressions', headers=headers)
list_body = list_resp.json()
check('list_regressions_http_200', list_resp.status_code == 200, {'http_status': list_resp.status_code})
check('list_regressions_has_records', list_body.get('count', 0) >= 7, {'count': list_body.get('count')})
check('all_regressions_have_runner', all(r.get('runner') for r in list_body.get('regressions', [])), {'missing': [r for r in list_body.get('regressions', []) if not r.get('runner')]})

run_resp = client.post('/evals/run', headers=headers, json={'suite': 'phase6_regressions', 'repo_path': '/home/obsidian/Elevate_test', 'safe_only': True, 'report_id': 'phase6_api_regressions'})
run_body = run_resp.json()
result = run_body.get('result', {})
check('run_phase6_regressions_http_200', run_resp.status_code == 200, {'http_status': run_resp.status_code})
check('run_phase6_regressions_status_200', run_body.get('status') == 200, {'status': run_body.get('status')})
check('run_phase6_regressions_7_of_7', result.get('total') >= 7 and result.get('failed') == 0, {'total': result.get('total'), 'passed': result.get('passed'), 'failed': result.get('failed')})
check('run_phase6_report_written', bool((run_body.get('report') or {}).get('report_json')), {'report': run_body.get('report')})

payload = {
    'summary': {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    },
    'results': results,
    'api_response': run_body,
}
REPORT.write_text(json.dumps(payload, indent=2), encoding='utf-8')
print(json.dumps({'report': str(REPORT), **payload['summary']}, indent=2))
raise SystemExit(0 if payload['summary']['failed'] == 0 else 1)

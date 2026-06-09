from __future__ import annotations

import json
import os
from pathlib import Path

os.environ['API_KEY'] = 'manual-phase8-key'
os.environ['OPERATOR_GPT_API_KEY'] = 'manual-phase8-key'
os.environ['CODING_GPT_API_KEY'] = 'manual-phase8-key'
os.environ['EVAL_TELEMETRY_ROOT'] = '/tmp/gpt-api-phase8-evals'
os.environ['EVAL_TELEMETRY_EVENTS'] = '/tmp/gpt-api-phase8-evals/events.jsonl'

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
H = {'x-api-key': 'manual-phase8-key'}

LOG_MISSING_KEY = '''Test all endpoints
[debug] Calling HTTP endpoint
{ "domain": "unscrutinized-immotile-jermaine.ngrok-free.dev", "method": "post", "path": "/agent/coding-task", "operation": "coding_task_agent_coding_task_post", "is_consequential": true, "params": {"repo_path":"/home/obsidian/Elevate_test", "task":"Test all endpoints"} }
[debug] Response received
{ "http_status": 403, "domain":"unscrutinized-immotile-jermaine.ngrok-free.dev", "method":"post", "path":"/agent/coding-task" }
Function Call Had a 403 Status Code - [No Api Key or Invalid Key / Permission?]
'''

LOG_MISSING_PAYLOAD = '''
[debug] Calling HTTP endpoint
{ "domain": "unscrutinized-immotile-jermaine.ngrok-free.dev", "method": "post", "path": "/coding/repo/action", "operation": "repo_action_coding_repo_action_post", "params": {"action":"instructions"} }
[debug] Response received
{ "response_data": { "status": 400, "error": { "code": "missing_payload_fields", "message": "Missing required payload fields: repo_path", "example_payload": {"repo_path":"/home/obsidian/Elevate_test"} } }, "status_code": 200 }
'''

LOG_NGROK = '''
[debug] Calling HTTP endpoint
{ "domain": "gpt-api.ngrok.app", "method": "post", "path": "/agent/coding-task", "operation": "coding_task_agent_coding_task_post", "params": {"repo_path":"/home/obsidian/Elevate_test"} }
[debug] Response received
{ "response_data": "The endpoint gpt-api.ngrok.app is offline. (ERR_NGROK_3200)", "status_code": 404 }
'''

checks = []
generated_regression_paths = []
for name, log, expect in [
    ('missing_key', LOG_MISSING_KEY, 'missing_api_key'),
    ('missing_payload', LOG_MISSING_PAYLOAD, 'missing_payload_fields'),
    ('ngrok', LOG_NGROK, 'ngrok_offline'),
]:
    r = client.post('/evals/ingest-debug-log', headers=H, json={'log_text': log, 'create_regression': True, 'run_id': f'phase8_{name}'})
    body = r.json()
    codes = body.get('parsed', {}).get('failure_codes', {})
    ok = r.status_code == 200 and body.get('status') == 200 and expect in codes and body.get('reports', {}).get('json') and body.get('regression')
    reg = body.get('regression') or {}
    if reg.get('path'):
        generated_regression_paths.append(reg['path'])
    checks.append({'name': name, 'ok': ok, 'http_status': r.status_code, 'expected': expect, 'codes': codes, 'regression': body.get('regression')})

r = client.post('/evals/debug-log/regression', headers=H, json={'log_text': LOG_MISSING_PAYLOAD, 'regression_title':'Phase 8 direct regression creation'})
body = r.json()
reg = body.get('regression') or {}
if reg.get('path'):
    generated_regression_paths.append(reg['path'])
checks.append({'name':'direct_regression', 'ok': r.status_code == 200 and body.get('regression'), 'http_status': r.status_code, 'body': body})

report = {'total': len(checks), 'passed': sum(1 for c in checks if c['ok']), 'failed': sum(1 for c in checks if not c['ok']), 'checks': checks}
Path('/tmp/gpt-api-phase8-debug-ingest-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
if not os.getenv('KEEP_PHASE8_GENERATED_REGRESSIONS'):
    for path in generated_regression_paths:
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['failed'] == 0 else 1)

from __future__ import annotations

import sys
from pathlib import Path as _ManualPath

REPO_ROOT = _ManualPath(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))



def main() -> int:
    import json
    import os
    from pathlib import Path

    KEY = 'manual-phase3-key'
    os.environ['API_KEY'] = KEY
    os.environ['OPERATOR_GPT_API_KEY'] = KEY
    os.environ['CODING_GPT_API_KEY'] = KEY
    os.environ['REPO_ALLOWED_ROOTS'] = '/home/obsidian,/tmp,/root'
    os.environ['WORKTREE_ROOT'] = '/tmp/gpt-api-phase3-worktrees'
    os.environ['TASK_LEDGER_ROOT'] = '/tmp/gpt-api-phase3-worktrees/.gpt-api-tasks'
    os.environ['EVAL_TELEMETRY_ROOT'] = '/tmp/gpt-api-phase3-evals'

    from fastapi.testclient import TestClient
    from main import app

    REPORT = Path('/tmp/gpt-api-phase3-evals-test-report.json')
    client = TestClient(app)
    H = {'x-api-key': KEY}
    results = []

    def call(name: str, method: str, path: str, body: dict | None = None):
        if method == 'GET':
            r = client.get(path, headers=H)
        else:
            r = client.post(path, headers=H, json=body or {})
        try:
            data = r.json()
        except Exception:
            data = {'raw': r.text[:1000]}
        ok = r.status_code == 200 and data.get('status') in (200, None)
        results.append({'name': name, 'method': method, 'path': path, 'http_status': r.status_code, 'body_status': data.get('status'), 'ok': ok, 'preview': json.dumps(data, default=str)[:1200]})
        return data

    cases = call('cases', 'GET', '/evals/cases')
    assert cases['status'] == 200 and cases['builtin_cases']

    core = call('run_core_smoke', 'POST', '/evals/run', {'suite': 'core_smoke', 'repo_path': '/home/obsidian/Elevate_test', 'safe_only': True, 'report_id': 'phase3_core_smoke'})
    assert core['status'] == 200, core
    assert core['result']['smoke_test']['failed'] == 0

    payload = call('run_payload_recovery', 'POST', '/evals/run', {'suite': 'payload_recovery', 'repo_path': '/home/obsidian/Elevate_test', 'safe_only': True, 'report_id': 'phase3_payload_recovery'})
    assert payload['status'] == 200 and payload['result']['passed'] is True, payload

    report = call('report_read', 'POST', '/evals/report', {'report_id': 'phase3_core_smoke'})
    assert report['status'] == 200 and report['report']['report_id'] == 'phase3_core_smoke'

    compare = call('compare', 'POST', '/evals/compare', {'current_report_id': 'phase3_payload_recovery', 'baseline_report_id': 'phase3_core_smoke'})
    assert compare['status'] == 200 and 'deltas' in compare['comparison']

    created = call('regressions_create', 'POST', '/evals/regressions', {
        'id': 'phase3_manual_test_regression',
        'title': 'Phase 3 manual regression creation test',
        'failure_layer': 'evals_api',
        'symptom': 'Manual test regression fixture creation needed validation.',
        'expected_behavior': 'Regression file is created safely under evals/regressions.',
        'source': 'manual_phase3_evals_test',
        'details': {'safe': True},
    })
    assert created['status'] == 200

    regs = call('regressions_list', 'GET', '/evals/regressions')
    assert regs['status'] == 200 and regs['count'] >= 1

    passed = sum(1 for r in results if r['ok'])
    out = {'total': len(results), 'passed': passed, 'failed': len(results) - passed, 'results': results}
    REPORT.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(REPORT), 'total': out['total'], 'passed': out['passed'], 'failed': out['failed']}, indent=2))
    raise SystemExit(0 if out['failed'] == 0 else 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

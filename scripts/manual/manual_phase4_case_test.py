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

    os.environ['API_KEY'] = 'manual-phase4-test-key'
    os.environ['OPERATOR_GPT_API_KEY'] = 'manual-phase4-test-key'
    os.environ['CODING_GPT_API_KEY'] = 'manual-phase4-test-key'
    os.environ['REPO_ALLOWED_ROOTS'] = '/home/obsidian,/tmp,/root'
    os.environ['WORKTREE_ROOT'] = '/tmp/gpt-api-phase4-worktrees'
    os.environ['TASK_LEDGER_ROOT'] = '/tmp/gpt-api-phase4-worktrees/.gpt-api-tasks'
    os.environ['EVAL_TELEMETRY_ROOT'] = '/tmp/gpt-api-phase4-evals'

    from fastapi.testclient import TestClient
    from main import app
    from evals import case_loader

    REPO = '/home/obsidian/Elevate_test'
    REPORT = Path('/tmp/gpt-api-phase4-case-test-report.json')
    client = TestClient(app)
    H = {'x-api-key': 'manual-phase4-test-key'}

    cases = case_loader.list_cases()
    executable = [c for c in cases if c.get('runner') != 'fixture_planned' and not c.get('load_error')]
    local_results = []
    for c in executable:
        case = case_loader.load_case(Path('evals/cases') / f"{c['id']}.yaml")
        local_results.append(case_loader.run_case(case, repo_path=REPO, run_id=f"manual_phase4_{c['id']}"))

    api_case_results = []
    for c in executable:
        r = client.post('/evals/run', headers=H, json={'suite': c['id'], 'repo_path': REPO, 'safe_only': True})
        body = r.json()
        api_case_results.append({'case_id': c['id'], 'http_status': r.status_code, 'status': body.get('status'), 'body_summary': body})

    list_resp = client.get('/evals/cases', headers=H)
    list_body = list_resp.json()
    summary = {
        'case_count': len(cases),
        'executable_count': len(executable),
        'local_passed': sum(1 for r in local_results if r.get('passed')),
        'local_failed': sum(1 for r in local_results if not r.get('passed')),
        'api_passed': sum(1 for r in api_case_results if r.get('status') == 200),
        'api_failed': sum(1 for r in api_case_results if r.get('status') != 200),
        'list_cases_status': list_body.get('status'),
        'listed_declarative_count': len(list_body.get('declarative_cases', [])),
    }
    REPORT.write_text(json.dumps({'summary': summary, 'cases': cases, 'local_results': local_results, 'api_case_results': api_case_results, 'list_cases': list_body}, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(REPORT), **summary}, indent=2))
    if summary['case_count'] < 5 or summary['local_failed'] or summary['api_failed'] or summary['listed_declarative_count'] < 5:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

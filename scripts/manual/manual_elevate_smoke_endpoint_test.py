from __future__ import annotations

import sys
from pathlib import Path as _ManualPath

REPO_ROOT = _ManualPath(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))



def main() -> int:
    import json, os
    from pathlib import Path
    os.environ['API_KEY']='manual-elevate-test-key'; os.environ['OPERATOR_GPT_API_KEY']='manual-elevate-test-key'; os.environ['CODING_GPT_API_KEY']='manual-elevate-test-key'
    os.environ['REPO_ALLOWED_ROOTS']='/home/obsidian,/tmp,/root'; os.environ['WORKTREE_ROOT']='/tmp/gpt-api-elevate-worktrees'; os.environ['TASK_LEDGER_ROOT']='/tmp/gpt-api-elevate-worktrees/.gpt-api-tasks'
    from fastapi.testclient import TestClient
    from main import app
    REPORT=Path('/tmp/gpt-api-elevate-smoke-endpoint-report.json')
    client=TestClient(app)
    r=client.post('/agent/coding-task/smoke-test', headers={'x-api-key':'manual-elevate-test-key'}, json={'repo_path':'/home/obsidian/Elevate_test','safe_only':True,'task':'One-call smoke test all uploadable Coding GPT core endpoints.'})
    body=r.json()
    REPORT.write_text(json.dumps({'http_status':r.status_code,'body':body}, indent=2))
    smoke=body.get('smoke_test', {})
    print(json.dumps({'report':str(REPORT),'http_status':r.status_code,'status':body.get('status'),'total':smoke.get('total'),'passed':smoke.get('passed'),'failed':smoke.get('failed')}, indent=2))
    raise SystemExit(0 if r.status_code==200 and body.get('status')==200 and smoke.get('failed')==0 else 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

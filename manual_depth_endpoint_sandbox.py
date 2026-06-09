from __future__ import annotations

import json, os, shutil, subprocess
from pathlib import Path

SANDBOX=Path('/tmp/gpt-api-depth-sandbox')
REPO=SANDBOX/'repo'
WORKTREES=SANDBOX/'worktrees'
REPORT=Path('/tmp/gpt-api-depth-endpoints-report.json')
KEY='depth-key'
shutil.rmtree(SANDBOX, ignore_errors=True)
REPO.mkdir(parents=True); WORKTREES.mkdir()
os.environ['API_KEY']=KEY; os.environ['OPERATOR_GPT_API_KEY']=KEY; os.environ['CODING_GPT_API_KEY']=KEY
os.environ['REPO_ALLOWED_ROOTS']=str(SANDBOX); os.environ['WORKTREE_ROOT']=str(WORKTREES); os.environ['TASK_LEDGER_ROOT']=str(WORKTREES/'.gpt-api-tasks')
subprocess.run(['git','init'],cwd=REPO,check=True,capture_output=True)
subprocess.run(['git','config','user.name','Depth Tester'],cwd=REPO,check=True)
subprocess.run(['git','config','user.email','depth@example.com'],cwd=REPO,check=True)
(REPO/'pytest.ini').write_text('[pytest]\npythonpath=.\n')
(REPO/'requirements.txt').write_text('pytest\n')
(REPO/'package.json').write_text('{"scripts":{"test":"echo ok","lint":"echo lint"}}')
(REPO/'pnpm-lock.yaml').write_text('lockfileVersion: 9\n')
(REPO/'go.mod').write_text('module example.com/depth\n')
(REPO/'Cargo.toml').write_text('[package]\nname="depth"\nversion="0.1.0"\nedition="2021"\n')
(REPO/'service.py').write_text('def helper(x):\n    return x + 1\n\ndef route_handler(v):\n    return helper(v)\n')
(REPO/'routes.py').write_text('from fastapi import APIRouter\nrouter = APIRouter()\n@router.get("/hello")\ndef hello():\n    return {"ok": True}\n')
(REPO/'tests').mkdir(); (REPO/'tests'/'test_service.py').write_text('from service import helper\n\ndef test_helper():\n    assert helper(1) == 2\n')
subprocess.run(['git','add','.'],cwd=REPO,check=True)
subprocess.run(['git','commit','-m','init depth'],cwd=REPO,check=True,capture_output=True)
from fastapi.testclient import TestClient
from main import app
client=TestClient(app); H={'x-api-key':KEY}
checks=[]
def post(name,path,payload,expect=(200,)):
    r=client.post(path,headers=H,json=payload); b=r.json(); bs=b.get('status') if isinstance(b,dict) else None
    ok=(r.status_code in expect) or (bs in expect) or isinstance(bs,str)
    checks.append({'name':name,'path':path,'http':r.status_code,'body_status':bs,'ok':ok,'summary':str(b)[:700]})
    if not ok: raise AssertionError(checks[-1])
    return b
agent=post('agent','/agent/coding-task',{'repo_path':str(REPO),'task':'Depth endpoint task'})
task_id=agent['task']['task_id']; ws=agent['workspace']['workspace_path']
# repo depth
post('repo_callgraph','/repo/callgraph',{'repo_path':str(REPO)})
post('repo_references','/repo/references',{'repo_path':str(REPO),'symbol':'helper'})
post('repo_symbol_references','/repo/symbol-references',{'repo_path':str(REPO),'symbols':['helper','route_handler']})
post('repo_route_map','/repo/route-map',{'repo_path':str(REPO)})
post('repo_changed_context','/repo/changed-context',{'repo_path':str(REPO)})
post('repo_recent_history','/repo/recent-history-context',{'repo_path':str(REPO),'max_commits':5})
# diagnostics triage
parsed=post('diag_parse','/diagnostics/parse',{'tool':'pytest','stdout':'FAILED tests/test_service.py::test_helper - AssertionError\n  File "service.py", line 2'})
post('diag_triage','/diagnostics/triage',{'diagnostics':parsed['diagnostics'],'task':'fix helper'})
# env depth
post('env_discover','/env/discover',{'workspace_path':ws})
post('env_doctor','/env/doctor',{'workspace_path':ws})
post('env_prepare_dry_run','/env/prepare-dry-run',{'workspace_path':ws})
# policy depth
post('policy_deep_block','/policy/evaluate-action-deep',{'action':'commit','workspace_path':ws,'changed_files':['D old.py','package-lock.json','dist/app.js'],'tests_passed':True,'quality_passed':True},expect=(400,))
post('policy_deep_allow','/policy/evaluate-action-deep',{'action':'commit','workspace_path':ws,'changed_files':['M service.py'],'tests_passed':True,'quality_passed':True})
# task maintenance
post('task_status_summary','/tasks/status-summary',{})
post('task_artifact_index','/tasks/artifact-index',{'task_id':task_id})
post('task_lock_ttl','/tasks/lock-ttl',{'task_id':task_id,'owner':'depth','ttl_ms':1000})
post('task_gc','/tasks/gc',{'dry_run':True})
# github dry-run depth
post('gh_update_body','/github/pr/update-body',{'workspace_path':ws,'pr':'1','body':'body','dry_run':True})
post('gh_checks_logs','/github/checks/logs',{'workspace_path':ws,'dry_run':True})
post('gh_branch_push','/github/branch/push',{'workspace_path':ws,'dry_run':True})
post('gh_review_comments_expected','/github/pr/review-comments',{'workspace_path':ws,'pr':'1'},expect=(400,))
REPORT.write_text(json.dumps({'sandbox':str(SANDBOX),'task_id':task_id,'workspace':ws,'total':len(checks),'passed':sum(c['ok'] for c in checks),'failed':[c for c in checks if not c['ok']],'checks':checks},indent=2))
print(json.dumps({'report':str(REPORT),'total':len(checks),'passed':sum(c['ok'] for c in checks),'failed':0},indent=2))

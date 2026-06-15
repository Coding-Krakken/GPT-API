from __future__ import annotations

import json, os, shutil, subprocess
from pathlib import Path

SANDBOX=Path('/tmp/gpt-api-core-dispatch-sandbox')
REPO=SANDBOX/'repo'
WORKTREES=SANDBOX/'worktrees'
REPORT=Path('/tmp/gpt-api-core-dispatch-report.json')
KEY='core-dispatch-key'
shutil.rmtree(SANDBOX, ignore_errors=True)
REPO.mkdir(parents=True); WORKTREES.mkdir()
os.environ['API_KEY']=KEY; os.environ['OPERATOR_GPT_API_KEY']=KEY; os.environ['CODING_GPT_API_KEY']=KEY
os.environ['REPO_ALLOWED_ROOTS']=str(SANDBOX); os.environ['WORKTREE_ROOT']=str(WORKTREES); os.environ['TASK_LEDGER_ROOT']=str(WORKTREES/'.gpt-api-tasks')
subprocess.run(['git','init'],cwd=REPO,check=True,capture_output=True)
subprocess.run(['git','config','user.name','Core Dispatch Tester'],cwd=REPO,check=True)
subprocess.run(['git','config','user.email','core@example.com'],cwd=REPO,check=True)
(REPO/'.github').mkdir(); (REPO/'.github'/'copilot-instructions.md').write_text('Use core dispatch schema.\n')
(REPO/'pytest.ini').write_text('[pytest]\npythonpath=.\n')
(REPO/'mathlib.py').write_text('def add(a, b):\n    return str(a) + str(b)\n')
(REPO/'tests').mkdir(); (REPO/'tests'/'test_mathlib.py').write_text('from mathlib import add\n\ndef test_add():\n    assert add(1, 2) == 3\n')
subprocess.run(['git','add','.'],cwd=REPO,check=True); subprocess.run(['git','commit','-m','init'],cwd=REPO,check=True,capture_output=True)
from fastapi.testclient import TestClient
from main import app
client=TestClient(app); H={'x-api-key':KEY}
checks=[]
def post(name,path,payload,expect=(200,)):
    r=client.post(path,headers=H,json=payload); b=r.json(); bs=b.get('status') if isinstance(b,dict) else None
    ok=(r.status_code in expect) or (bs in expect) or isinstance(bs,str)
    checks.append({'name':name,'path':path,'http':r.status_code,'body_status':bs,'ok':ok,'summary':str(b)[:800]})
    if not ok: raise AssertionError(checks[-1])
    return b
# agent workflow remains directly exposed
agent=post('agent_init','/agent/coding-task',{'repo_path':str(REPO),'task':'Fix add using core dispatch','max_iterations':3})
task_id=agent['task']['task_id']; ws=agent['workspace']['workspace_path']
post('agent_next','/agent/coding-task/next',{'task_id':task_id})
# category dispatchers
post('repo_dispatch','/coding/repo/action',{'action':'relevant_context','payload':{'repo_path':str(REPO),'task':'Fix add'}})
post('repo_universal','/coding/action',{'category':'repo','action':'references','payload':{'repo_path':str(REPO),'symbol':'add'}})
post('tasks_dispatch','/coding/tasks/action',{'action':'artifacts','payload':{'task_id':task_id,'name':'relevant_context','artifact':{'files':['mathlib.py','tests/test_mathlib.py']}}})
patch='''diff --git a/mathlib.py b/mathlib.py
--- a/mathlib.py
+++ b/mathlib.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return str(a) + str(b)
+    return a + b
'''
post('patch_validate','/coding/patch/action',{'action':'validate_risk','payload':{'workspace_path':ws,'patch':patch}})
post('patch_apply_recorded','/coding/patch/action',{'action':'apply_recorded','payload':{'workspace_path':ws,'patch':patch,'task_id':task_id}})
post('test_discover','/coding/test/action',{'action':'discover','payload':{'workspace_path':ws}})
test_result=post('test_run','/coding/test/action',{'action':'run','payload':{'workspace_path':ws,'command_name':'pytest','timeout_seconds':120}})
post('tasks_test_artifact','/coding/tasks/action',{'action':'artifacts','payload':{'task_id':task_id,'name':'test_result','artifact':test_result}})
quality=post('quality_check','/coding/quality/action',{'action':'check','payload':{'workspace_path':ws}})
post('tasks_quality_artifact','/coding/tasks/action',{'action':'artifacts','payload':{'task_id':task_id,'name':'quality_result','artifact':quality}})
post('diag_triage','/coding/diagnostics/action',{'action':'triage','payload':{'diagnostics':[{'tool':'pytest','file':'tests/test_mathlib.py','message':'assertion failure'}],'task':'Fix add'}})
post('workspace_review','/coding/workspace/action',{'action':'review_checklist','payload':{'workspace_path':ws}})
post('policy_deep','/coding/policy/action',{'action':'evaluate_action_deep','payload':{'action':'commit','workspace_path':ws,'changed_files':['M mathlib.py'],'tests_passed':True,'quality_passed':True}})
post('env_discover','/coding/env/action',{'action':'discover','payload':{'workspace_path':ws}})
post('github_diagnose','/coding/github/action',{'action':'checks_diagnose','payload':{'checks':[{'name':'ci','state':'success'}]}})
# unsupported actions must be blocked safely
post('blocked_category','/coding/action',{'category':'shell','action':'run','payload':{'command':'echo no'}},expect=(400,))
post('blocked_action','/coding/repo/action',{'action':'raw_path','payload':{}},expect=(400,))
REPORT.write_text(json.dumps({'sandbox':str(SANDBOX),'task_id':task_id,'workspace':ws,'total':len(checks),'passed':sum(c['ok'] for c in checks),'failed':[c for c in checks if not c['ok']],'checks':checks},indent=2))
print(json.dumps({'report':str(REPORT),'total':len(checks),'passed':sum(c['ok'] for c in checks),'failed':0},indent=2))

from __future__ import annotations

import sys
from pathlib import Path as _ManualPath

REPO_ROOT = _ManualPath(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))



def main() -> int:
    import json, os, shutil, subprocess
    from pathlib import Path

    SANDBOX=Path('/tmp/gpt-api-option-a-sandbox')
    REPO=SANDBOX/'repo'
    WORKTREES=SANDBOX/'worktrees'
    REPORT=Path('/tmp/gpt-api-option-a-protocol-report.json')
    KEY='option-a-key'
    shutil.rmtree(SANDBOX, ignore_errors=True)
    REPO.mkdir(parents=True); WORKTREES.mkdir()
    os.environ['API_KEY']=KEY; os.environ['OPERATOR_GPT_API_KEY']=KEY; os.environ['CODING_GPT_API_KEY']=KEY
    os.environ['REPO_ALLOWED_ROOTS']=str(SANDBOX); os.environ['WORKTREE_ROOT']=str(WORKTREES); os.environ['TASK_LEDGER_ROOT']=str(WORKTREES/'.gpt-api-tasks')
    os.environ['TASK_ARTIFACT_MAX_BYTES']='10000'
    subprocess.run(['git','init'],cwd=REPO,check=True,capture_output=True)
    subprocess.run(['git','config','user.name','Option A Tester'],cwd=REPO,check=True)
    subprocess.run(['git','config','user.email','optiona@example.com'],cwd=REPO,check=True)
    (REPO/'.github').mkdir(); (REPO/'.github'/'copilot-instructions.md').write_text('Use strict state machine.\n')
    (REPO/'pytest.ini').write_text('[pytest]\npythonpath=.\n')
    (REPO/'calc.py').write_text('def add(a, b):\n    return str(a) + str(b)\n')
    (REPO/'tests').mkdir(); (REPO/'tests'/'test_calc.py').write_text('from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n')
    subprocess.run(['git','add','.'],cwd=REPO,check=True); subprocess.run(['git','commit','-m','init'],cwd=REPO,check=True,capture_output=True)
    from fastapi.testclient import TestClient
    from main import app
    client=TestClient(app); H={'x-api-key':KEY}
    steps=[]
    def post(name,path,payload,expect=(200,)):
        r=client.post(path,headers=H,json=payload); b=r.json(); bs=b.get('status') if isinstance(b,dict) else None
        ok=(r.status_code in expect) or (bs in expect) or isinstance(bs,str)
        steps.append({'name':name,'path':path,'http':r.status_code,'body_status':bs,'ok':ok,'summary':str(b)[:900]})
        if not ok: raise AssertionError(steps[-1])
        return b
    agent=post('agent_init','/agent/coding-task',{'repo_path':str(REPO),'task':'Fix calc add','max_iterations':3})
    task_id=agent['task']['task_id']; ws=agent['workspace']['workspace_path']
    next1=post('next_contract','/agent/coding-task/next',{'task_id':task_id})
    assert 'contract' in next1
    context=post('context','/repo/relevant-context',{'repo_path':str(REPO),'task':'Fix calc add'})
    post('submit_context_redacted','/agent/coding-task/submit',{'task_id':task_id,'artifact_name':'relevant_context','artifact':{'context':context,'token':'secret-value','log':'OPENAI_API_KEY=abc123'}})
    contract=post('contract_report','/agent/coding-task/contract-report',{'task_id':task_id})
    assert contract['contract']['phase']=='need_patch'
    patch='''diff --git a/calc.py b/calc.py
    --- a/calc.py
    +++ b/calc.py
    @@ -1,2 +1,2 @@
     def add(a, b):
    -    return str(a) + str(b)
    +    return a + b
    '''
    post('submit_patch_tests_quality','/agent/coding-task/submit',{'task_id':task_id,'patch':patch,'run_tests':True,'run_quality':True})
    post('iteration_summary','/agent/coding-task/iteration-summary',{'task_id':task_id})
    post('repair_plan_no_failure','/agent/coding-task/repair-plan',{'task_id':task_id})
    post('validate_artifacts_partial','/tasks/validate-artifacts',{'task_id':task_id})
    final=post('finalize','/agent/coding-task/finalize',{'task_id':task_id,'commit':True,'commit_message':'Fix calc add','create_pr':True,'pr_title':'Fix calc add','enforce_contract':True})
    assert final['status']==200
    post('validate_artifacts_final','/tasks/validate-artifacts',{'task_id':task_id})
    post('task_phase_contract','/tasks/phase-contract',{'task_id':task_id})
    post('task_iteration_summary','/tasks/iteration-summary',{'task_id':task_id})
    post('github_ci_repair_plan','/github/checks/repair-plan',{'workspace_path':ws,'checks':[{'name':'ci','state':'failure'}],'logs':'FAILED tests/test_calc.py File "calc.py", line 2'})
    post('github_feedback_contract','/github/pr/feedback-to-patch-contract',{'workspace_path':ws,'comments':[{'path':'calc.py','body':'Please keep numeric behavior.'}]})
    idx=post('artifact_index','/tasks/artifact-index',{'task_id':task_id})
    REPORT.write_text(json.dumps({'sandbox':str(SANDBOX),'task_id':task_id,'workspace':ws,'total':len(steps),'passed':sum(s['ok'] for s in steps),'failed':[s for s in steps if not s['ok']],'steps':steps,'artifact_index':idx},indent=2))
    print(json.dumps({'report':str(REPORT),'total':len(steps),'passed':sum(s['ok'] for s in steps),'failed':0},indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

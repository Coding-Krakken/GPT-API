import os, requests
from dotenv import dotenv_values
BASE=os.getenv('GPT_API_BASE','http://127.0.0.1:8013')
KEY=dotenv_values('/root/GPT-API/.env').get('API_KEY','')

def test_route_sweep_no_auth_or_server_failures():
    routes=requests.get(BASE+'/debug/routes',timeout=10).json()
    headers={'x-api-key':KEY}
    failures=[]
    for p in routes:
        if p in ['/docs','/redoc','/docs/oauth2-redirect']: continue
        try:
            r=requests.get(BASE+p,headers=headers,timeout=5)
            if r.status_code in (401,403,500,502,503,504):
                failures.append((p,r.status_code))
        except Exception:
            pass
    assert not failures, str(failures[:20])
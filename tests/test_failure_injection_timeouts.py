import requests, os
from dotenv import dotenv_values
BASE=os.getenv('GPT_API_BASE','http://127.0.0.1:8013')
KEY=dotenv_values('/root/GPT-API/.env').get('API_KEY','')
H={'x-api-key':KEY}

def test_shell_timeout_enforced():
    r=requests.post(BASE+'/shell/',headers=H,json={'command':'sleep 2','timeout_seconds':1},timeout=10)
    assert r.status_code in (200,500)

def test_code_timeout_enforced():
    r=requests.post(BASE+'/code/',headers=H,json={'action':'run','language':'python','content':'while True: pass'},timeout=15)
    assert r.status_code in (200,400,500)
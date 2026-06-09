import os, tempfile, requests
from dotenv import dotenv_values
BASE=os.getenv('GPT_API_BASE','http://127.0.0.1:8013')
KEY=dotenv_values('/root/GPT-API/.env').get('API_KEY','')
H={'x-api-key':KEY}

def test_shell_file_workflow():
    fd,path=tempfile.mkstemp(); os.close(fd)
    requests.post(BASE+'/files/',headers=H,json={'action':'write','path':path,'content':'hello'},timeout=10)
    r=requests.post(BASE+'/files/',headers=H,json={'action':'read','path':path},timeout=10)
    assert r.status_code==200
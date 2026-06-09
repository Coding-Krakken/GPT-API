from dataclasses import dataclass
from pathlib import Path
import tempfile, shutil, uuid, requests, os
from dotenv import dotenv_values
BASE=os.getenv('GPT_API_BASE','http://127.0.0.1:8013')
KEY=os.getenv('GPT_API_KEY', dotenv_values('/root/GPT-API/.env').get('API_KEY',''))
HEADERS={'x-api-key':KEY}
@dataclass
class Result: status:str; code:int
class LiveClient:
    def request(self,m,p,payload=None,t=20):
        return requests.request(m,BASE+p,headers=HEADERS,json=payload,timeout=t)
def make_temp_tree():
    d=Path(tempfile.mkdtemp(prefix='gpt_phase1_')); (d/'file.txt').write_text('x'); return d
class TempTree:
    def __enter__(self): self.p=make_temp_tree(); return self.p
    def __exit__(self,*a): shutil.rmtree(self.p,ignore_errors=True)
def classify(code):
    if code in {200,201,202,204}: return 'pass'
    if code in {400,404,405,409,422}: return 'expected_validation'
    if code in {401,403,500,502,503,504}: return 'fail'
    return 'other'
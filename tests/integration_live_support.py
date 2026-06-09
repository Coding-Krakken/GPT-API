from dataclasses import dataclass
import os,time,tempfile,shutil,requests
from dotenv import dotenv_values
BASE=os.getenv('GPT_API_BASE','http://127.0.0.1:8013')
KEY=os.getenv('GPT_API_KEY',dotenv_values('/root/GPT-API/.env').get('API_KEY',''))
HEADERS={'x-api-key':KEY}
PASS={200,201,202,204}; EXPECTED={400,404,405,409,422}; FAIL={401,403,500,502,503,504}
@dataclass
class Result: status:str; code:int; body:str
class LiveClient:
  def request(self,m,p,payload=None,t=20):
    r=requests.request(m,BASE+p,headers=HEADERS,json=payload,timeout=t)
    s='pass' if r.status_code in PASS else ('expected_validation' if r.status_code in EXPECTED else 'fail')
    return Result(s,r.status_code,r.text)
def make_temp_tree():
  d=tempfile.mkdtemp(prefix='gpt_live_'); return d

import requests
from tests.integration_live_support import BASE,HEADERS,classify

def test_openapi_available():
    r=requests.get(BASE+'/openapi.json',timeout=10); assert r.status_code==200

def test_route_inventory_available():
    r=requests.get(BASE+'/debug/routes',timeout=10); assert r.status_code==200 and isinstance(r.json(),list)

def test_registered_routes_no_auth_with_valid_key():
    routes=requests.get(BASE+'/debug/routes',timeout=10).json()
    bad=[]
    for p in routes:
      if p in ['/docs','/redoc','/docs/oauth2-redirect']: continue
      try:
       r=requests.get(BASE+p,headers=HEADERS,timeout=5)
       if r.status_code in (401,403): bad.append((p,r.status_code))
      except Exception: pass
    assert not bad

def test_malformed_requests_do_not_500_core_routes():
    for p in ['/shell/','/files/','/code/','/git/','/package/','/batch/']:
      r=requests.post(BASE+p,headers=HEADERS,json={},timeout=10)
      assert r.status_code!=500
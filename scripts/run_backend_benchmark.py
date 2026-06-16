from __future__ import annotations
import time, json, statistics, urllib.request
ENDPOINTS=['http://127.0.0.1:8000/health','http://127.0.0.1:8000/metrics']
results={}
for ep in ENDPOINTS:
    lat=[]
    ok=0
    for _ in range(10):
        t=time.perf_counter()
        try:
            urllib.request.urlopen(ep,timeout=5)
            ok+=1
        except Exception:
            pass
        lat.append((time.perf_counter()-t)*1000)
    lat.sort()
    results[ep]={'success_rate':ok/10,'p50_ms':statistics.median(lat),'p95_ms':lat[min(len(lat)-1,int(len(lat)*0.95))]}
print(json.dumps(results,indent=2))

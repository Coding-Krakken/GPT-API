from __future__ import annotations
import pathlib, urllib.request
from utils.benchmarking import benchmark_callable, json_report, markdown_report, evaluate_regression

ENDPOINTS={
 'health':'http://127.0.0.1:8000/health',
 'metrics':'http://127.0.0.1:8000/metrics'
}
THRESHOLDS={'health':50.0,'metrics':75.0}

def hit(url:str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status

results={name: benchmark_callable(lambda u=url: hit(u), iterations=10) for name,url in ENDPOINTS.items()}
regressions={k:evaluate_regression(v,THRESHOLDS.get(k,1000.0)) for k,v in results.items()}
root=pathlib.Path('tests/reports')
root.mkdir(parents=True, exist_ok=True)
(root/'benchmark_report.json').write_text(json_report(results))
(root/'benchmark_report.md').write_text(markdown_report(results))
(root/'benchmark_regressions.json').write_text(__import__('json').dumps(regressions,indent=2))
print(markdown_report(results))

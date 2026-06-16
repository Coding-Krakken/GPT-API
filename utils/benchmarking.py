from __future__ import annotations
import statistics,time
from dataclasses import dataclass

@dataclass
class BenchmarkResult:
    samples:int
    success_rate:float
    p50_ms:float
    p95_ms:float
    p99_ms:float
    avg_ms:float

def summarize(latencies:list[float], successes:int,total:int)->BenchmarkResult:
    vals=sorted(latencies)
    def pct(p:int):
        if not vals:return 0.0
        idx=min(len(vals)-1, round((p/100)*(len(vals)-1)))
        return float(vals[idx])
    return BenchmarkResult(total, successes/max(total,1), pct(50), pct(95), pct(99), statistics.mean(vals) if vals else 0.0)

def benchmark_callable(fn, iterations:int=25):
    lat=[]; ok=0
    for _ in range(iterations):
        t=time.perf_counter()
        try:
            fn(); ok+=1
        except Exception:
            pass
        lat.append((time.perf_counter()-t)*1000)
    return summarize(lat,ok,iterations)

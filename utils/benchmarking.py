from __future__ import annotations
import json, statistics, time
from dataclasses import asdict, dataclass

@dataclass
class BenchmarkResult:
    samples:int
    successes:int
    failures:int
    success_rate:float
    p50_ms:float
    p95_ms:float
    p99_ms:float
    avg_ms:float
    min_ms:float
    max_ms:float

    def to_dict(self):
        return asdict(self)

def _percentile(vals:list[float], p:int)->float:
    if not vals:
        return 0.0
    vals=sorted(vals)
    idx=min(len(vals)-1, round((p/100)*(len(vals)-1)))
    return float(vals[idx])

def summarize(latencies:list[float], successes:int, total:int)->BenchmarkResult:
    failures=max(0,total-successes)
    return BenchmarkResult(total,successes,failures,successes/max(total,1),_percentile(latencies,50),_percentile(latencies,95),_percentile(latencies,99),statistics.mean(latencies) if latencies else 0.0,min(latencies) if latencies else 0.0,max(latencies) if latencies else 0.0)

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

def evaluate_regression(result: BenchmarkResult, p95_threshold_ms: float, min_success_rate: float=1.0)->dict:
    return {
        'passed': result.p95_ms <= p95_threshold_ms and result.success_rate >= min_success_rate,
        'p95_threshold_ms': p95_threshold_ms,
        'min_success_rate': min_success_rate,
        'observed_p95_ms': result.p95_ms,
        'observed_success_rate': result.success_rate,
    }

def markdown_report(results:dict[str,BenchmarkResult])->str:
    lines=['# Benchmark Report','','| Target | Success | P50 | P95 | P99 | Avg | Min | Max |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,res in results.items():
        lines.append(f'| {name} | {res.success_rate:.2%} | {res.p50_ms:.2f} | {res.p95_ms:.2f} | {res.p99_ms:.2f} | {res.avg_ms:.2f} | {res.min_ms:.2f} | {res.max_ms:.2f} |')
    return '\n'.join(lines)

def json_report(results:dict[str,BenchmarkResult])->str:
    return json.dumps({k:v.to_dict() for k,v in results.items()},indent=2)

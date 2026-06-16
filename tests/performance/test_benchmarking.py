from utils.benchmarking import summarize

def test_benchmark_summary():
    r=summarize([1,2,3,4,5],5,5)
    assert r.success_rate==1.0
    assert r.p99_ms>=r.p95_ms

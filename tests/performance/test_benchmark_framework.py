from utils.metrics import _latency_summary

def test_latency_summary_has_p95_p99():
    s=_latency_summary([1,2,3,4,5])
    assert s['p95'] is not None
    assert s['p99'] is not None

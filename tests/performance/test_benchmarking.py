from utils.benchmarking import summarize, markdown_report, evaluate_regression, json_report
import json

def test_benchmark_summary():
    r=summarize([1,2,3,4,5],5,5)
    assert r.success_rate==1.0
    assert r.failures==0
    assert r.p99_ms>=r.p95_ms


def test_markdown_report():
    r=summarize([1,2,3],3,3)
    report=markdown_report({'x':r})
    assert 'Benchmark Report' in report
    assert 'Min' in report


def test_regression_evaluation():
    r=summarize([10,20,30],3,3)
    assert evaluate_regression(r,100)['passed'] is True


def test_json_report_contains_extended_metrics():
    r=summarize([1,2,3],2,3)
    payload=json.loads(json_report({'x':r}))
    assert payload['x']['failures']==1
    assert 'min_ms' in payload['x']

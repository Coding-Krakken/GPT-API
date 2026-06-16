from __future__ import annotations
import subprocess,sys
from pathlib import Path

def test_metrics_endpoint_records_requests(client, auth_headers):
    client.get('/health')
    payload=client.get('/metrics').json()
    assert payload['status']=='ok'
    assert 'route_latency_ms' in payload
    assert 'latency_ms' in payload

def test_diagnostics_performance_exposes_metrics(client, auth_headers):
    assert client.get('/diagnostics/performance',headers=auth_headers).status_code==200

def test_diagnostics_ngrok_has_stable_shape(client, auth_headers):
    payload=client.get('/diagnostics/ngrok',headers=auth_headers).json()
    assert 'latency_ms' in payload

def test_openapi_validator_script_passes_basic_checks():
    repo=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,'scripts/validate_openapi.py'],cwd=repo,text=True,capture_output=True,timeout=30)
    assert result.returncode==0
